"""
Activity 3.2 & 3.3: Pro Medical Dashboard
Displays a live-updating plot of ECG data alongside a dedicated
UI panel for real-time HRV, BPM, and PQRST metrics.
"""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from collections import deque
import logging
import os
import numpy as np
import neurokit2 as nk
from iacq import IACQ

# --- 1. Mute Logs ---
logging.getLogger('iacq').setLevel(logging.WARNING)
logging.getLogger('FPGAEmulator').setLevel(logging.WARNING)

TEST_KEY = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
TEST_NONCE = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
TEST_AD = b"A to B"
BUFFER_SIZE = 1800  # 5 seconds at 360 Hz

def load_all_waveforms(csv_path: str = "data/xNorm.csv") -> list[bytes]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")
    waveforms = []
    with open(csv_path, "r") as f:
        for line in f:
            if hex_str := line.strip():
                waveforms.append(bytes.fromhex(hex_str))
    return waveforms

waveforms = load_all_waveforms()
total_waveforms = len(waveforms)

fpga = IACQ(port='COM8', emulator=True)
fpga.open_connection()

# --- 2. Build the Pro UI Dashboard ---
app = QtWidgets.QApplication([])
main_window = QtWidgets.QWidget()
main_window.setWindowTitle("Advanced ASCON-128 Medical Dashboard")
main_window.resize(1200, 600)
main_window.setStyleSheet("background-color: #121212; color: white;") # Dark mode

# Main Layout (Horizontal: Plot left, Stats right)
layout = QtWidgets.QHBoxLayout()
main_window.setLayout(layout)

# --- Left Side: Clean ECG Plot ---
plot_widget = pg.PlotWidget(title="Live Decrypted ECG Stream")
plot_widget.setLabel('bottom', "Samples")
plot_widget.setLabel('left', "Amplitude")
plot_widget.setYRange(0, 255)
plot_widget.setXRange(0, BUFFER_SIZE)
plot_widget.showGrid(x=True, y=True, alpha=0.3)
curve = plot_widget.plot(pen=pg.mkPen(color='#ff3333', width=2.5))

layout.addWidget(plot_widget, stretch=3) # Takes 75% of screen

# --- Right Side: Medical Stats Panel ---
stats_layout = QtWidgets.QVBoxLayout()

title_label = QtWidgets.QLabel("PATIENT METRICS")
title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #888888;")

bpm_label = QtWidgets.QLabel("HR: -- BPM")
bpm_label.setStyleSheet("font-size: 48px; font-weight: bold; color: #ff3333;")

hrv_sdnn_label = QtWidgets.QLabel("SDNN: -- ms")
hrv_sdnn_label.setStyleSheet("font-size: 20px; color: #aaaaaa;")

hrv_rmssd_label = QtWidgets.QLabel("RMSSD: -- ms")
hrv_rmssd_label.setStyleSheet("font-size: 20px; color: #aaaaaa;")

hrv_pnn50_label = QtWidgets.QLabel("pNN50: -- %")
hrv_pnn50_label.setStyleSheet("font-size: 20px; color: #aaaaaa;")

pqrst_label = QtWidgets.QLabel("QRS Duration: -- ms")
pqrst_label.setStyleSheet("font-size: 20px; color: #aaaaaa;")

status_label = QtWidgets.QLabel("STATUS: ANALYZING...")
status_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffb74d;")

# Add widgets to the right panel in logical order
stats_layout.addWidget(title_label)
stats_layout.addSpacing(30)
stats_layout.addWidget(bpm_label)
stats_layout.addSpacing(15)
stats_layout.addWidget(hrv_sdnn_label)
stats_layout.addWidget(hrv_rmssd_label)
stats_layout.addWidget(hrv_pnn50_label)
stats_layout.addWidget(pqrst_label) # Grouped with the other metrics
stats_layout.addSpacing(40)
stats_layout.addWidget(status_label)
stats_layout.addStretch() # Pushes everything to the top

stats_widget = QtWidgets.QWidget()
stats_widget.setLayout(stats_layout)
layout.addWidget(stats_widget, stretch=1) # Takes 25% of screen

buffer = deque(maxlen=BUFFER_SIZE)
frame_idx = 0

# --- 3. Logic & Timers ---
def update_gui():
    """Ultra-fast rendering loop."""
    global frame_idx
    waveform = waveforms[frame_idx % total_waveforms]
    frame_idx += 1

    ciphertext, tag = fpga.encrypt_on_fpga(waveform, TEST_KEY, TEST_NONCE, TEST_AD)
    decrypted = fpga.decrypt_waveform(ciphertext, tag, TEST_KEY, TEST_NONCE, TEST_AD)

    buffer.extend(list(decrypted))
    curve.setData(list(buffer))

def update_analysis():
    """Heavy mathematical processing loop."""
    if len(buffer) < 1000: 
        return

    try:
        current_data = list(buffer)
        ecg_cleaned = nk.ecg_clean(current_data, sampling_rate=360)
        _, peaks_info = nk.ecg_peaks(ecg_cleaned, sampling_rate=360)
        rpeaks = peaks_info["ECG_R_Peaks"]

        if len(rpeaks) > 1:
            # 1. Calculate BPM & HRV
            rr_intervals = np.diff(rpeaks) / 360 * 1000  # ms
            bpm = 60000 / np.mean(rr_intervals)
            sdnn = np.std(rr_intervals)
            rmssd = np.sqrt(np.mean(np.diff(rr_intervals)**2))
            pnn50 = 100 * np.sum(np.abs(np.diff(rr_intervals)) > 50) / len(rr_intervals)
            
            # 2. Delineate PQRST
            _, waves = nk.ecg_delineate(ecg_cleaned, rpeaks, sampling_rate=360, method="dwt")
            q_peaks = [x for x in waves.get('ECG_Q_Peaks', []) if not np.isnan(x)]
            s_peaks = [x for x in waves.get('ECG_S_Peaks', []) if not np.isnan(x)]
            
            # 3. Update UI Strings Safely
            bpm_label.setText(f"HR: {bpm:.0f} BPM")
            hrv_sdnn_label.setText(f"SDNN: {sdnn:.1f} ms")
            hrv_rmssd_label.setText(f"RMSSD: {rmssd:.1f} ms")
            hrv_pnn50_label.setText(f"pNN50: {pnn50:.1f} %")

            if len(q_peaks) > 0 and len(s_peaks) > 0:
                min_len = min(len(q_peaks), len(s_peaks))
                qrs_duration = np.mean(np.array(s_peaks[:min_len]) - np.array(q_peaks[:min_len])) / 360 * 1000
                pqrst_label.setText(f"QRS Duration: {qrs_duration:.1f} ms")

            # 4. Dynamic Status Alert
            if bpm > 100:
                status_label.setText("STATUS: TACHYCARDIA")
                status_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #ff3333;") # Red
            elif bpm < 60:
                status_label.setText("STATUS: BRADYCARDIA")
                status_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #4fc3f7;") # Blue
            else:
                status_label.setText("STATUS: NORMAL")
                status_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #81c784;") # Green
    except Exception:
        pass

# Start timers
gui_timer = QtCore.QTimer()
gui_timer.timeout.connect(update_gui)
gui_timer.start(25)

analysis_timer = QtCore.QTimer()
analysis_timer.timeout.connect(update_analysis)
analysis_timer.start(1000)

if __name__ == '__main__':
    print("Starting Pro Medical Dashboard...")
    main_window.show()
    try:
        app.exec_()
    finally:
        fpga.close_connection()
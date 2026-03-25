"""
TP3: Ultimate Secure Medical Monitor
Author: Ronald Marín
"""

import sys
import os
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from collections import deque
import logging
import numpy as np
import neurokit2 as nk
from iacq import IACQ

# --- 1. Configurations ---
logging.getLogger('iacq').setLevel(logging.WARNING)
logging.getLogger('FPGAEmulator').setLevel(logging.WARNING)

TEST_KEY = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
TEST_INITIAL_NONCE = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
TEST_AD = b"A to B"
BUFFER_SIZE = 1800 
SAMPLING_RATE = 360

def load_all_waveforms(csv_path: str = "data/xNorm.csv"):
    """Load all valid waveforms from the specified CSV file.

    Args:
        csv_path (str, optional): Path to the CSV dataset. Defaults to "data/xNorm.csv".

    Returns:
        list[bytes]: A list of parsed waveforms as byte arrays.

    Raises:
        FileNotFoundError: If the CSV file does not exist.

    Example:
        >>> waveforms = load_all_waveforms("data/xNorm.csv")
    """
    if not os.path.exists(csv_path): raise FileNotFoundError(f"Dataset not found")
    waveforms = []
    with open(csv_path, "r") as f:
        for line in f:
            if hex_str := line.strip(): waveforms.append(bytes.fromhex(hex_str))
    return waveforms

ALL_WAVEFORMS = load_all_waveforms()
TOTAL_WAVEFORMS = len(ALL_WAVEFORMS)

class MedicalDashboard(QtWidgets.QMainWindow):
    """The Ultimate Secure Medical Dashboard using PyQt5 and PyQtGraph.
    
    Provides an advanced, real-time visualization of decrypted ECG data, 
    heart rate trends, and a Poincaré map for HRV analysis.
    """

    def __init__(self, fpga_instance: IACQ):
        """Initialize the Ultimate Medical Dashboard.

        Args:
            fpga_instance (IACQ): An active instance of the IACQ connection class.

        Example:
            >>> fpga = IACQ('COM8', emulator=True)
            >>> window = MedicalDashboard(fpga)
        """
        super().__init__()
        self.fpga = fpga_instance
        self.frame_idx = 0
        self.buffer = deque(maxlen=BUFFER_SIZE)
        self.bpm_history = deque(maxlen=60)
        
        # Historial para Poincaré (nube persistente)
        self.poincare_x = deque(maxlen=500)
        self.poincare_y = deque(maxlen=500)
        
        self.is_paused = True 
        self.current_nonce = TEST_INITIAL_NONCE
        self.last_tag_str = "WAITING..." # Variable segura para el tag
        
        self.setWindowTitle("Ultimate Secure Medical Dashboard - ASCON-128")
        self.resize(1400, 850)
        self.setStyleSheet("background-color: #0b0e14; color: #e0e0e0;")

        self.init_ui()
        self.init_timers()

    def init_ui(self):
        """Build and configure the Dashboard's UI layout, plots, and statistical panels."""
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.grid = QtWidgets.QGridLayout(self.central_widget)

        # --- 1. Main ECG Plot (Top Left) ---
        self.ecg_plot = pg.PlotWidget(title="LIVE DECRYPTED ECG")
        self.ecg_plot.setYRange(0, 255)
        self.ecg_curve = self.ecg_plot.plot(pen=pg.mkPen(color='#00ff00', width=2))
        self.grid.addWidget(self.ecg_plot, 0, 0, 1, 2)

        # --- 2. HR Trend (Bottom Left) ---
        self.trend_plot = pg.PlotWidget(title="HEART RATE TREND (BPM)")
        self.trend_plot.setYRange(40, 140)
        self.trend_curve = self.trend_plot.plot(pen=pg.mkPen(color='#ff3333', width=2), symbol='o', symbolSize=4)
        self.grid.addWidget(self.trend_plot, 1, 0, 1, 1)

        # --- 3. Poincaré Plot (Bottom Center) ---
        self.poincare_plot = pg.PlotWidget(title="POINCARÉ MAP (RR_n vs RR_n+1)")
        self.poincare_plot.setLabel('left', "RR_n+1 (ms)")
        self.poincare_plot.setLabel('bottom', "RR_n (ms)")
        
        # Línea roja de identidad arreglada (pos=[0,0])
        self.identity_line = pg.InfiniteLine(pos=[0, 0], angle=45, pen=pg.mkPen(color='#ff3333', width=1.5, style=QtCore.Qt.DashLine))
        self.poincare_plot.addItem(self.identity_line)
        
        self.poincare_scatter = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(0, 255, 255, 150))
        self.poincare_plot.addItem(self.poincare_scatter)
        self.grid.addWidget(self.poincare_plot, 1, 1, 1, 1)

        # --- 4. Controls & Stats (Right Side) ---
        self.stats_panel = QtWidgets.QVBoxLayout()
        
        # Fuentes más grandes
        self.bpm_display = QtWidgets.QLabel("-- BPM")
        self.bpm_display.setStyleSheet("font-size: 80px; font-weight: bold; color: #00ff00;")
        
        self.info_label = QtWidgets.QLabel("SDNN: -- ms\npNN50: -- %\nQRS: -- ms")
        self.info_label.setStyleSheet("font-size: 22px; color: #aaaaaa; line-height: 1.5;")
        
        # System Status Box Expandido
        self.status_box = QtWidgets.QLabel("SYSTEM STATUS WAITING...")
        self.status_box.setStyleSheet("""
            font-family: 'Consolas', monospace; font-size: 18px; color: #81c784; 
            background: #1a1f26; padding: 15px; border-radius: 8px; border: 1px solid #333;
        """)
        
        self.alert_label = QtWidgets.QLabel("STATUS: IDLE")
        self.alert_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #555;")

        self.btn = QtWidgets.QPushButton("START MONITOR")
        self.btn.setStyleSheet("background: #388e3c; color: white; padding: 20px; font-weight: bold; font-size: 22px; border-radius: 10px;")
        self.btn.clicked.connect(self.toggle_pause)

        # Añadimos todo al panel derecho
        self.stats_panel.addWidget(QtWidgets.QLabel("VITAL SIGNS"), 0, QtCore.Qt.AlignCenter)
        self.stats_panel.addWidget(self.bpm_display, 0, QtCore.Qt.AlignCenter)
        self.stats_panel.addWidget(self.info_label)
        self.stats_panel.addSpacing(20)
        self.stats_panel.addWidget(QtWidgets.QLabel("SYSTEM INFO"))
        self.stats_panel.addWidget(self.status_box)
        self.stats_panel.addStretch()
        self.stats_panel.addWidget(self.alert_label, 0, QtCore.Qt.AlignCenter)
        self.stats_panel.addWidget(self.btn)

        self.grid.addLayout(self.stats_panel, 0, 2, 2, 1)

    def init_timers(self):
        """Initialize the PyQt timers for the GUI rendering and medical analysis loops."""
        self.gui_timer = QtCore.QTimer()
        self.gui_timer.timeout.connect(self.update_stream)
        self.analysis_timer = QtCore.QTimer()
        self.analysis_timer.timeout.connect(self.update_analysis)

    def toggle_pause(self):
        """Toggle the monitoring state between paused and running.
        
        Updates the UI buttons and labels, and starts/stops the underlying timers.
        """
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.gui_timer.stop(); self.analysis_timer.stop()
            self.btn.setText("RESUME MONITOR"); self.btn.setStyleSheet("background: #388e3c; color: white; padding: 20px; font-weight: bold; font-size: 22px; border-radius: 10px;")
            self.alert_label.setText("STATUS: PAUSED")
            self.alert_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #555;")
        else:
            self.gui_timer.start(25); self.analysis_timer.start(1000)
            self.btn.setText("PAUSE MONITOR"); self.btn.setStyleSheet("background: #fbc02d; color: black; padding: 20px; font-weight: bold; font-size: 22px; border-radius: 10px;")
            self.alert_label.setText("STATUS: RUNNING")

    def update_stream(self):
        """High-speed rendering loop for the ASCON-128 encrypted data stream.
        
        Processes the next waveform through the FPGA, increments the cryptographic 
        nonce, and updates the live ECG plot buffer.
        """
        waveform = ALL_WAVEFORMS[self.frame_idx % TOTAL_WAVEFORMS]
        self.frame_idx += 1
        
        ct, tag = self.fpga.encrypt_on_fpga(waveform, TEST_KEY, self.current_nonce, TEST_AD)
        decrypted = self.fpga.decrypt_waveform(ct, tag, TEST_KEY, self.current_nonce, TEST_AD)
        
        # Guardamos el tag completo en Hex
        self.last_tag_str = tag.hex().upper()
        
        n_int = int.from_bytes(self.current_nonce, 'big') + 1
        self.current_nonce = n_int.to_bytes(16, 'big')

        self.buffer.extend(list(decrypted))
        self.ecg_curve.setData(list(self.buffer))

    def update_analysis(self):
        """Perform comprehensive mathematical and medical analysis on the ECG buffer.
        
        Uses NeuroKit2 to extract R-peaks, calculate heart rate, HRV metrics (SDNN, pNN50), 
        and QRS duration. Updates the Heart Rate Trend plot, Poincaré map, and system alerts.
        """
        if len(self.buffer) < 1000: return
        try:
            data = list(self.buffer)
            ecg_c = nk.ecg_clean(data, sampling_rate=360)
            _, p_info = nk.ecg_peaks(ecg_c, sampling_rate=360)
            rpeaks = p_info["ECG_R_Peaks"]

            if len(rpeaks) > 2:
                rr = np.diff(rpeaks) / 360 * 1000
                bpm = 60000 / np.mean(rr)
                
                # Update UI
                self.bpm_display.setText(f"{bpm:.0f} BPM")
                self.bpm_history.append(bpm)
                self.trend_curve.setData(list(self.bpm_history))
                
                # Poincaré Math: Acumular puntos
                self.poincare_x.extend(rr[:-1])
                self.poincare_y.extend(rr[1:])
                self.poincare_scatter.setData(list(self.poincare_x), list(self.poincare_y))
                
                # HRV & QRS
                sdnn = np.std(rr)
                pnn50 = 100 * np.sum(np.abs(np.diff(rr)) > 50) / len(rr)
                
                _, waves = nk.ecg_delineate(ecg_c, rpeaks, sampling_rate=360, method="dwt")
                q_p = [x for x in waves.get('ECG_Q_Peaks', []) if not np.isnan(x)]
                s_p = [x for x in waves.get('ECG_S_Peaks', []) if not np.isnan(x)]
                qrs_val = "N/A"
                if len(q_p) > 0 and len(s_p) > 0:
                    qrs_val = f"{np.mean(np.array(s_p[:min(len(q_p), len(s_p))]) - np.array(q_p[:min(len(q_p), len(s_p))])) / 360 * 1000:.1f}"

                self.info_label.setText(f"SDNN: {sdnn:.1f} ms\npNN50: {pnn50:.1f} %\nQRS: {qrs_val} ms")
                
                # Status Box Expandido y Seguro
                buffer_sec = len(self.buffer) / 360
                tag_format = f"{self.last_tag_str[:16]}\n      {self.last_tag_str[16:]}" if len(self.last_tag_str) > 16 else self.last_tag_str
                
                status_text = (
                    f"MODE: EMULATOR\n"
                    f"BAUD: 115200\n"
                    f"WAVE: {self.frame_idx % TOTAL_WAVEFORMS}\n"
                    f"BUFF: {buffer_sec:.1f}s ({len(self.buffer)} pts)\n"
                    f"TAG : {tag_format}"
                )
                self.status_box.setText(status_text)
                
                # Alertas
                if bpm > 100: 
                    self.alert_label.setText("⚠️ TACHYCARDIA")
                    self.alert_label.setStyleSheet("color: #ff3333; font-weight: bold; font-size: 28px;")
                elif bpm < 60: 
                    self.alert_label.setText("⚠️ BRADYCARDIA")
                    self.alert_label.setStyleSheet("color: #4fc3f7; font-weight: bold; font-size: 28px;")
                else: 
                    self.alert_label.setText("✅ NORMAL")
                    self.alert_label.setStyleSheet("color: #81c784; font-weight: bold; font-size: 28px;")
        except Exception as e:
            print(f"Error en analisis: {e}")

    def closeEvent(self, event):
        """Handle the window close event to safely terminate hardware connections.

        Args:
            event (QtGui.QCloseEvent): The close event triggered by the user.
        """
        self.fpga.close_connection()
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    fpga_conn = IACQ(port='COM8', emulator=True)
    fpga_conn.open_connection()
    dash = MedicalDashboard(fpga_conn)
    dash.show()
    sys.exit(app.exec_())
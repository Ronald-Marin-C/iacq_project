"""
Activity 3.2: Real-Time Visualization (High-Performance Version)
Displays a live-updating plot of ECG data running through the ASCON encryption pipeline.
Uses PyQtGraph for hardware-accelerated real-time rendering.
"""

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from collections import deque
import logging
from iacq import IACQ
import os

# --- 1. Mute non-critical logs ---
logging.getLogger('iacq').setLevel(logging.WARNING)
logging.getLogger('FPGAEmulator').setLevel(logging.WARNING)

# --- 2. Setup Parameters & Data ---
TEST_KEY = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
TEST_NONCE = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
TEST_AD = b"A to B"
BUFFER_SIZE = 1800  # 5 seconds of rolling window

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

# Initialize FPGA
fpga = IACQ(port='COM8', emulator=True)
fpga.open_connection()

# --- 3. Setup PyQtGraph Window ---
app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True, title="Real-Time Secure ECG Monitor")
win.resize(1000, 600)

plot = win.addPlot(title="ASCON-128 Decrypted Live ECG (Hardware Accelerated)")
plot.setLabel('bottom', "Samples (Rolling 5s window)")
plot.setLabel('left', "Amplitude (Raw)")
plot.setYRange(0, 255)
plot.setXRange(0, BUFFER_SIZE)
plot.showGrid(x=True, y=True, alpha=0.3)

# The red ECG line
curve = plot.plot(pen=pg.mkPen(color='#FF0000', width=2))

buffer = deque(maxlen=BUFFER_SIZE)
frame_idx = 0

def update():
    """Timer callback function for real-time updates"""
    global frame_idx
    
    # 1. Get new waveform
    waveform = waveforms[frame_idx % total_waveforms]
    frame_idx += 1

    # 2. Hardware Encryption Pipeline
    ciphertext, tag = fpga.encrypt_on_fpga(waveform, TEST_KEY, TEST_NONCE, TEST_AD)
    
    # 3. Software Decryption
    decrypted = fpga.decrypt_waveform(ciphertext, tag, TEST_KEY, TEST_NONCE, TEST_AD)

    # 4. Add to rolling buffer
    buffer.extend(list(decrypted))

    # 5. Update plot incredibly fast
    curve.setData(list(buffer))

# --- 4. Start Real-Time Loop ---
# QTimer handles the animation loop natively in the OS
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(25)  # 25 ms refresh rate (super smooth)

if __name__ == '__main__':
    print("Starting High-Performance Real-Time ECG Monitor...")
    print("Close the plot window to exit safely.")
    
    try:
        app.exec_()  # Starts the Qt event loop
    finally:
        print("Cleaning up hardware connection...")
        fpga.close_connection()
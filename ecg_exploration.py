"""
ECG Data Exploration script using PyQtGraph.
Reads normalized ECG data from a CSV file, parses hexadecimal strings,
verifies data length, and plots a single waveform identifying the R-peak.
Ready for future real-time streaming integration.
"""

import os
import pyqtgraph as pg
import logging
from pyqtgraph.Qt import QtWidgets



# Basic configuration for console output
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def explore_ecg_dataset(filepath: str) -> None:
    """Load, parse, and plot ECG data from the specified filepath using PyQtGraph.

    Reads normalized ECG data, parses hexadecimal strings into byte arrays,
    verifies that each waveform is exactly 181 bytes, and visualizes the
    first waveform along with its R-peak.

    Args:
        filepath (str): Path to the CSV file containing the ECG data in hexadecimal format.

    Example:
        >>> explore_ecg_dataset("data/xNorm.csv")
    """
    if not os.path.exists(filepath):
        logging.error(f"Error: File '{filepath}' not found.")
        return

    waveforms = []
    
    # 1. Load xNorm.csv and parse data
    with open(filepath, 'r') as file:
        lines = file.readlines()
        
        for line in lines:
            hex_string = line.strip()
            if not hex_string:
                continue
                
            # 2. Parse hex strings into byte arrays
            try:
                waveform_bytes = bytes.fromhex(hex_string)
            except ValueError as e:
                logging.error(f"Error parsing hex string: {e}")
                continue
                
            # 3. Verify each waveform is exactly 181 bytes
            if len(waveform_bytes) != 181:
                logging.warning(f"Warning: Found waveform with length {len(waveform_bytes)}")
                continue
                
            waveforms.append(waveform_bytes)

    # Count waveforms
    total_waveforms = len(waveforms)
    logging.info(f"Total valid waveforms loaded: {total_waveforms}")

    if total_waveforms == 0:
        logging.info("No valid waveforms found to plot.")
        return

    # Take the first waveform for analysis
    first_waveform = waveforms[0]
    amplitude_values = list(first_waveform)

    # 4. Calculate time duration
    sample_rate = 360  # Hz
    duration = len(amplitude_values) / sample_rate
    logging.info(f"Time duration of one waveform: {duration:.4f} seconds")

    time_axis = [i / sample_rate for i in range(len(amplitude_values))]

    # 5. Identify the R-peak
    r_peak_amplitude = max(amplitude_values)
    r_peak_index = amplitude_values.index(r_peak_amplitude)
    r_peak_time = time_axis[r_peak_index]
    
    logging.info(f"R-Peak identified at: Time = {r_peak_time:.4f}s, Amplitude = {r_peak_amplitude}")

    # ==========================================
    # PyQtGraph Visualization
    # ==========================================
    
    # Initialize Qt Application
    app = QtWidgets.QApplication([])
    
    # Create main window
    win = pg.GraphicsLayoutWidget(show=True, title="ECG Waveform Analysis")
    win.resize(1000, 600)
    win.setBackground('w') # White background for a cleaner look
    
    # Add plot area
    plot = win.addPlot(title="<span style='color: #000; font-size: 14pt;'>Single ECG Waveform (181 bytes)</span>")
    plot.setLabel('bottom', "Time", units='s', color='#000')
    plot.setLabel('left', "Amplitude (0-255)", color='#000')
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.addLegend()
    
    # Plot the ECG signal line
    pen = pg.mkPen(color='#1f77b4', width=2)
    plot.plot(time_axis, amplitude_values, pen=pen, name="ECG Signal")
    
    # Plot the R-Peak as a scatter point
    scatter = pg.ScatterPlotItem(
        x=[r_peak_time], 
        y=[r_peak_amplitude], 
        size=12, 
        pen=pg.mkPen(None), 
        brush=pg.mkBrush(255, 0, 0, 255), 
        name="R-Peak"
    )
    plot.addItem(scatter)
    
    # Start the Qt event loop
    QtWidgets.QApplication.instance().exec()

if __name__ == "__main__":
    csv_path = "data/xNorm.csv"
    explore_ecg_dataset(csv_path)
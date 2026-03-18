# IACQ - Secure ECG Acquisition Library

## Overview

The IACQ library provides a robust Python interface for communicating with an FPGA hardware accelerator. It implements the UART command protocol required to send ECG waveforms and perform ASCON-128 authenticated encryption. The library strictly follows the Fail-Fast principle, validating all cryptographic inputs before transmission.

## Installation

Ensure you have Python 3.10+ installed. It is recommended to use a virtual environment.

1. Clone this repository.
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

Here is a minimal example to establish a connection and set an encryption key:

```python
from iacq import IACQ
from exceptions import FPGAError

# Use a context manager for safe resource handling
try:
    with IACQ(port='COM8', emulator=False) as fpga:
        # Define a 16-byte key
        key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")

        # Send key to the FPGA
        fpga.send_key(key)
        print("Hardware ready for encryption!")

except FPGAError as e:
    print(f"FPGA Operation Failed: {e}")
```

## Hardware vs. Emulator Usage

This library supports both physical hardware and a software emulator for development without the FPGA board.

- **Hardware Mode:** Set `emulator=False` and provide the correct serial port (e.g., `'COM8'` on Windows or `'/dev/ttyUSB0'` on Linux). This uses `pyserial` to communicate with the physical board.

- **Emulator Mode:** Set `emulator=True` (the `port` parameter is ignored). This routes all communication through the `FPGAEmulator` class, simulating hardware delays and ASCON cryptography locally.

## Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| `ConnectionRefusedError` | Port is already in use by another program (e.g., Vivado or another terminal). | Close the other application holding the COM port and retry. |
| `FPGATimeoutError` | Incorrect baud rate or disconnected board. | Verify the board is plugged in and the baud rate is set to `115200`. |
| `FPGAValidationError` | Incorrect data type or length. | Ensure keys and nonces are exactly 16 bytes and passed as `bytes` objects, not strings. |
| No Logs Output | Emulators overriding the logging configuration. | Ensure `logger.propagate = False` is set in your main script configuration. |



Sphinx

pdoc3
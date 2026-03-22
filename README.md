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


# Session 2 Notes - Ronald Marín

## 1. Encryption Protocol

### Command Sequence
1. K - Load encryption key (16 bytes)
2. N - Set nonce (16 bytes)
3. A - Set associated data (padded to 10 bytes)
4. W - Send waveform data (padded to 184 bytes)
5. G - Start encryption
6. T - Retrieve authentication tag (16 bytes)
7. C - Retrieve ciphertext (181 bytes extracted from 184 bytes)

### Flow Diagram
```text
[Plaintext Waveform 181B] + [Padding 3B]
           |
           v
+-------------------------+
| FPGA Hardware (ASCON)   | <--- Key (16B), Nonce (16B), AD
+-------------------------+
           |
           v
[Ciphertext 181B] + [Tag 16B]


Sphinx


Q8
Why might code work in the emulator but fail on hardware?

The emulator uses different encryption
Hardware has physical delays and limited buffers
Python behaves differently with hardware
The FPGA has a different protocol

## Performance Benchmarking
To verify the system's readiness for real-time medical monitoring, a stress test was conducted using the full encryption/decryption pipeline.

### Test Configuration
- **Dataset:** 5,000 ECG waveforms (181 bytes each).
- **Mode:** FPGA Emulator (simulated UART @ 115200 baud).
- **Operations per cycle:** 7 UART commands (K, N, A, W, G, T, C) + Python-side ASCON decryption.

### Results
| Metric | Value |
| :--- | :--- |
| **Total Processed** | 5,000 waveforms |
| **Success Rate** | 100% (0 errors) |
| **Avg. Latency per Cycle** | 125.44 ms |
| **System Throughput** | **7.97 waveforms/sec** |

**Analysis:** With a throughput of nearly 8 waveforms per second, the system is ~8x faster than a standard human heart rate (60 BPM / 1 Hz). This provides a significant safety margin for real-time processing, even during high-stress physiological conditions (tachycardia) or multi-sensor environments.
pdoc3
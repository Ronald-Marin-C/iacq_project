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

## Running the Application

The Quick Start section above shows how to use the library programmatically. To run the full application with the real-time ECG dashboard, simply execute:

```bash
python visualization.py
```

## Hardware vs. Emulator Usage

This library supports both physical hardware and a software emulator for development without the FPGA board.

- **Hardware Mode:** Set `emulator=False` and provide the correct serial port (e.g., `'COM8'` on Windows or `'/dev/ttyUSB0'` on Linux). This uses `pyserial` to communicate with the physical board.

- **Emulator Mode:** Set `emulator=True` (the `port` parameter is ignored). This routes all communication through the `FPGAEmulator` class, simulating hardware delays and ASCON cryptography locally.

> **⚠️ Why code that works in the emulator may fail on hardware:**
> The emulator runs entirely in software, so it has no timing constraints or memory limits. The physical FPGA board introduces **real propagation delays** between commands and operates with **limited internal buffers**. If commands are sent too fast or data exceeds buffer capacity, the board may drop bytes or return unexpected responses. Always add appropriate delays between UART commands when running on hardware and verify your baud rate is set to `115200`.

## Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| `ConnectionRefusedError` | Port is already in use by another program (e.g., Vivado or another terminal). | Close the other application holding the COM port and retry. |
| `FPGATimeoutError` | Incorrect baud rate or disconnected board. | Verify the board is plugged in and the baud rate is set to `115200`. |
| `FPGAValidationError` | Incorrect data type or length. | Ensure keys and nonces are exactly 16 bytes and passed as `bytes` objects, not strings. |
| No Logs Output | Emulators overriding the logging configuration. | Ensure `logger.propagate = False` is set in your main script configuration. |

---

## Encryption Protocol

### Command Sequence

The FPGA communication follows a strict 7-step command sequence:

1. `K` — Load encryption key (16 bytes)
2. `N` — Set nonce (16 bytes)
3. `A` — Set associated data (padded to 10 bytes)
4. `W` — Send waveform data (padded to 184 bytes)
5. `G` — Start encryption
6. `T` — Retrieve authentication tag (16 bytes)
7. `C` — Retrieve ciphertext (181 bytes extracted from 184 bytes)

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
```

---

## Performance Benchmarking

To verify the system's readiness for real-time medical monitoring, a stress test was conducted using the full encryption/decryption pipeline.

### Test Configuration

- **Dataset:** 5,000 ECG waveforms (181 bytes each)
- **Mode:** FPGA Emulator (simulated UART @ 115200 baud)
- **Operations per cycle:** 7 UART commands (K, N, A, W, G, T, C) + Python-side ASCON decryption

### Results

| Metric | Value |
| :--- | :--- |
| **Total Processed** | 5,000 waveforms |
| **Success Rate** | 100% (0 errors) |
| **Avg. Latency per Cycle** | 125.44 ms |
| **System Throughput** | **7.97 waveforms/sec** |

**Analysis:** With a throughput of nearly 8 waveforms per second, the system is ~8x faster than a standard human heart rate (60 BPM / 1 Hz). This provides a significant safety margin for real-time processing, even during high-stress physiological conditions (tachycardia) or multi-sensor environments.

---

## Security Analysis: The Danger of Nonce Reuse

This project includes a formal security test suite (`tests/test_security.py`) to validate ASCON-128 AEAD properties. Beyond standard Bit-Flip and Wrong-Key tests, we implemented a specific test demonstrating **Nonce Reuse vulnerabilities**.

Unlike standard stream ciphers where nonce reuse leaks the XOR of the entire plaintext, ASCON utilizes a **Sponge Construction**. Our tests successfully prove that:

1. Reusing a nonce perfectly leaks the XOR of the plaintexts **only for the first block** (the 8-byte rate of ASCON-128).
2. After the first difference, the internal sponge state diverges, protecting the rest of the message.

This demonstrates both the vulnerability of poor nonce management and the resilience of the sponge architecture.

---

## Hardware Authenticity (Bitstream Verification)

To verify that the hardware implementation was compiled locally rather than using pre-compiled binaries, SHA-256 hashes were computed for the generated bitstreams. Vivado embeds unique build timestamps, ensuring unique binaries even for identical source code.

| File | SHA-256 Hash |
| :--- | :--- |
| `inter_spartan.bit` (Provided) | `32A3810828796B11F369C86B1876A3DEF37AEAFB29CC6C2835153BA1B8F0A3FD` |
| `ECG.bit` (Custom Build) | `199AF6DE57FE0944A77803C650EF321CBA33B535B2859A36E3174A79230E2057` |

*Hashes mismatch confirms the authenticity of the local Vivado synthesis and implementation.*

---

## Advanced Features

### 1. Advanced GUI Application

The standard visualization was transformed into a full **Qt5 Graphical User Interface (`visualization.py`)**. This professional dashboard features:

- **Separated Layouts:** ECG Plot (75% screen) separate from Medical Metrics (25%).
- **Hardware Acceleration:** Using `pyqtgraph` to maintain high frame rates even with real-time decryption.
- **Interactive Controls:** A user-controllable **Pause/Resume** button that directly controls the encryption/decryption loop and the neuro-signal processing threads.

### 2. Arrhythmia Screening (NeuroKit2 Integration)

Instead of just displaying raw heart rate, the dashboard integrates a real-time medical analysis engine:

- **Dynamic Thresholding:** Automatically detects and flags **Tachycardia** (>100 BPM), **Bradycardia** (<60 BPM), or **Irregular Rhythms** (via HRV/QRS duration) with color-coded visual alerts.
- **Advanced HRV:** Calculation of pNN50 and RMSSD metrics to assess autonomic nervous system balance.
- **PQRST Delineation:** Calculation of precise **QRS Duration** for more detailed cardiac analysis.

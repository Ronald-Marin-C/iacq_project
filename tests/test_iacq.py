"""
Test suite for the IACQ class: Full Pipeline Demonstration.
Runs the complete encrypt/decrypt system with continuous data
and measures performance metrics.
"""

import time
import os
import logging
from iacq import IACQ

# Configure logging for the test script
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('FPGAEmulator').setLevel(logging.WARNING)

def load_all_waveforms(csv_path: str = "data/xNorm.csv") -> list[bytes]:
    """Load all waveforms from the CSV file."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    waveforms = []
    with open(csv_path, "r") as f:
        for line in f:
            hex_str = line.strip()
            if hex_str:
                waveforms.append(bytes.fromhex(hex_str))
    return waveforms

def run_pipeline(fpga: IACQ, waveforms: list[bytes], key: bytes, nonce: bytes, associated_data: bytes) -> None:
    """Run encrypt/decrypt pipeline on multiple waveforms and calculate metrics."""
    results = []
    errors = 0
    total_waveforms = len(waveforms)

    logger.info(f"Starting pipeline processing for {total_waveforms} waveforms...")
    logger.info("-" * 50)

    for i, waveform in enumerate(waveforms):
        # Start the stopwatch
        start = time.perf_counter()

        try:
            # 1. Encrypt on FPGA (Hardware/Emulator)
            ciphertext, tag = fpga.encrypt_on_fpga(waveform, key, nonce, associated_data)

            # 2. Decrypt in Python (Software)
            decrypted = fpga.decrypt_waveform(ciphertext, tag, key, nonce, associated_data)

            # Stop the stopwatch
            elapsed = time.perf_counter() - start

            # 3. Verify Integrity
            if decrypted == waveform:
                results.append(elapsed)
            else:
                errors += 1
                logger.error(f"Waveform {i}: DATA MISMATCH ERROR")
                
        except Exception as e:
            errors += 1
            logger.error(f"Waveform {i}: EXCEPTION ENCOUNTERED -> {e}")

        # Progress indicator (log every 100 waveforms to avoid spamming the console)
        if (i + 1) % 100 == 0 or (i + 1) == total_waveforms:
            logger.info(f"Processed {i + 1}/{total_waveforms} waveforms...")

    # ==========================================
    # PERFORMANCE METRICS SUMMARY
    # ==========================================
    logger.info("-" * 50)
    logger.info("PIPELINE DEMONSTRATION SUMMARY")
    logger.info("-" * 50)
    
    avg_time = sum(results) / len(results) if results else 0
    logger.info(f"Processed successfully : {len(results)} waveforms")
    logger.info(f"Errors / Dropped data  : {errors}")
    logger.info(f"Avg time per cycle     : {avg_time * 1000:.2f} ms")
    
    if avg_time > 0:
        throughput = 1 / avg_time
        logger.info(f"System Throughput      : {throughput:.2f} waveforms/sec")
    logger.info("-" * 50)

if __name__ == "__main__":
    # 1. Setup Parameters
    TEST_KEY = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
    TEST_NONCE = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
    TEST_AD = b"A to B"
    
    try:
        # 2. Load continuous data (path is relative to the root folder where we run the script)
        all_waveforms = load_all_waveforms("data/xNorm.csv")
        
        # 3. Execute with Context Manager
        with IACQ(port='COM8', emulator=True) as fpga_device:
            run_pipeline(fpga_device, all_waveforms, TEST_KEY, TEST_NONCE, TEST_AD)
            
    except Exception as e:
        logger.error(f"Fatal test error: {e}")
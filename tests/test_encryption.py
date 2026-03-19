"""
ASCON Encryption/Decryption Test Script.
Validates the software implementation of ASCON-128 using ECG waveforms.
"""

import matplotlib.pyplot as plt
import os
from ascon_pcsn import ascon_encrypt, ascon_decrypt

# 1. Setup Encryption Parameters
# Using provided values for future FPGA comparison
KEY = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
NONCE = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
ASSOCIATED_DATA = b"A to B"

def load_waveform_from_csv(csv_path: str, index: int = 0) -> bytes:
    """Load a single 181-byte waveform from the ECG dataset.

    Args:
        csv_path (str): Path to the CSV file containing ECG data in hex format.
        index (int, optional): The line index of the waveform to load. Defaults to 0.

    Returns:
        bytes: The parsed 181-byte ECG waveform.

    Raises:
        FileNotFoundError: If the dataset file does not exist at the given path.
        ValueError: If the loaded waveform is not exactly 181 bytes.
        IndexError: If the requested index is out of bounds in the CSV.

    Example:
        >>> waveform = load_waveform_from_csv("data/xNorm.csv", index=5)
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at {csv_path}")

    with open(csv_path, "r") as f:
        for i, line in enumerate(f):
            if i == index:
                waveform = bytes.fromhex(line.strip())
                if len(waveform) != 181:
                    raise ValueError(f"Waveform at index {index} is {len(waveform)} bytes (expected 181)")
                return waveform
    raise IndexError(f"Waveform index {index} not found in CSV")

def run_test():
    """Execute the full encryption/decryption test cycle.

    Loads an ECG waveform, encrypts it using ASCON-128, verifies that the 
    decrypted data matches the original, and visualizes the results using Matplotlib.

    Example:
        >>> run_test()
    """
    # 2. Load the first waveform (index 0)
    try:
        csv_path = "data/xNorm.csv"
        waveform = load_waveform_from_csv(csv_path, index=0)
        print(f"Original Waveform loaded: {len(waveform)} bytes")
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # 3. Encrypt the waveform
    # Returns concatenated (ciphertext + tag) in the reference code
    # But ascon_encrypt in ascon_pcsn returns them separately? 
    # Let's check: in the provided ascon_pcsn.py, ascon_encrypt returns 'ciphertext + tag'
    # but the Activity says 'ciphertext, tag = ascon_encrypt(...)'. 
    # Let's adapt to your specific ascon_pcsn.py:
    
    full_result = ascon_encrypt(KEY, NONCE, ASSOCIATED_DATA, waveform)
    ciphertext = full_result[:-16]
    tag = full_result[-16:]

    print(f"Encryption successful!")
    print(f"Ciphertext length: {len(ciphertext)} bytes")
    print(f"Auth Tag: {tag.hex().upper()}")
    print(f"Ciphertext Sample (first 10 bytes): {ciphertext[:10].hex().upper()}")

    # 4. Decrypt and verify
    # In your ascon_pcsn.py, ascon_decrypt needs the tag as part of the ciphertext
    decrypted = ascon_decrypt(KEY, NONCE, ASSOCIATED_DATA, ciphertext + tag)

    if decrypted == waveform:
        print("\n[SUCCESS] Decrypted data matches the original waveform perfectly!")
    else:
        print("\n[ERROR] Decrypted data mismatch.")
        return

    # 5. Visualization with Matplotlib (3-panel comparison)
    # Using Matplotlib here as it's better for static subplot reports
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # Plot Original
    axes[0].plot(list(waveform), color="#1f77b4")
    axes[0].set_title("1. Original ECG Waveform (Plaintext)")
    axes[0].set_ylabel("Amplitude")
    axes[0].grid(True, alpha=0.3)

    # Plot Ciphertext
    axes[1].plot(list(ciphertext), color="#d62728")
    axes[1].set_title("2. Encrypted ECG (Ciphertext) - Looks like white noise")
    axes[1].set_ylabel("Amplitude")
    axes[1].grid(True, alpha=0.3)

    # Plot Decrypted
    axes[2].plot(list(decrypted), color="#2ca02c")
    axes[2].set_title("3. Decrypted ECG (Recovered Plaintext)")
    axes[2].set_ylabel("Amplitude")
    axes[2].set_xlabel("Sample Index")
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    run_test()
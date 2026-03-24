"""
Activity 3.4: Security Testing
Formal test suite to verify ASCON-128 AEAD security properties:
Confidentiality, Integrity, Correctness, and the dangers of Nonce Reuse.
"""

import os
import logging
from iacq import IACQ
from exceptions import FPGAAuthenticationError

# Mute standard logs so our test results are clean
logging.getLogger('iacq').setLevel(logging.CRITICAL)
logging.getLogger('FPGAEmulator').setLevel(logging.CRITICAL)

def load_waveform(index=0, csv_path="data/xNorm.csv"):
    """Load a specific single waveform by its line index from a CSV file.

    Args:
        index (int, optional): The zero-based line index of the waveform to load. Defaults to 0.
        csv_path (str, optional): Path to the CSV file containing ECG data. Defaults to "data/xNorm.csv".

    Returns:
        bytes | None: The parsed ECG waveform as bytes, or None if the index is out of bounds.

    Example:
        >>> waveform_b = load_waveform(index=1)
        >>> if waveform_b:
        ...     print(f"Loaded {len(waveform_b)} bytes")
    """
    with open(csv_path, "r") as f:
        for i, line in enumerate(f):
            if i == index:
                return bytes.fromhex(line.strip())
    return None

def run_security_tests():
    """Execute the formal security test suite for the ASCON-128 AEAD implementation.

    Tests confidentiality (wrong key), integrity (modified ciphertext), 
    correctness (wrong nonce), and demonstrates the vulnerability of nonce reuse 
    (information leak) using the connected FPGA or emulator.

    Example:
        >>> run_security_tests()
    """
    print("="*50)
    print(" ASCON-128 AEAD Security Test Suite ")
    print("="*50)
    
    # Base setup
    key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
    nonce = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
    ad = b"A to B"
    
    waveform_a = load_waveform(index=0)
    waveform_b = load_waveform(index=1)

    with IACQ(port='COM8', emulator=True) as fpga:
        
        # ---------------------------------------------------------
        print("\n[Test 1] Wrong Key (Confidentiality)")
        ct, tag = fpga.encrypt_on_fpga(waveform_a, key, nonce, ad)
        wrong_key = os.urandom(16)
        try:
            fpga.decrypt_waveform(ct, tag, wrong_key, nonce, ad)
            print("❌ FAIL: Decryption should have been rejected")
        except FPGAAuthenticationError:
            print("✅ PASS: Wrong key correctly rejected")

        # ---------------------------------------------------------
        print("\n[Test 2] Modified Ciphertext - Bit Flip (Integrity)")
        modified = bytearray(ct)
        modified[0] ^= 0x01  # Flip the least significant bit
        try:
            fpga.decrypt_waveform(bytes(modified), tag, key, nonce, ad)
            print("❌ FAIL: Modified ciphertext should be rejected")
        except FPGAAuthenticationError:
            print("✅ PASS: Tampered data correctly detected")

        # ---------------------------------------------------------
        print("\n[Test 3] Wrong Nonce (Correctness)")
        wrong_nonce = os.urandom(16)
        try:
            fpga.decrypt_waveform(ct, tag, key, wrong_nonce, ad)
            print("❌ FAIL: Wrong nonce should be rejected")
        except FPGAAuthenticationError:
            print("✅ PASS: Wrong nonce correctly rejected")

        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        print("\n[Test 4a] Naive Nonce Reuse (Standard Stream Cipher Assumption)")
        # Encrypt two different waveforms with the SAME nonce
        ct_a, tag_a = fpga.encrypt_on_fpga(waveform_a, key, nonce, ad)
        ct_b, tag_b = fpga.encrypt_on_fpga(waveform_b, key, nonce, ad) 
        
        # XOR the full ciphertexts and plaintexts
        xor_ct_full = bytes(a ^ b for a, b in zip(ct_a, ct_b))
        xor_pt_full = bytes(a ^ b for a, b in zip(waveform_a, waveform_b))
        
        if xor_ct_full == xor_pt_full:
            print("❌ FAIL: Full XOR matched (This would mean ASCON is a pure stream cipher, which is false)")
        else:
            print("✅ PASS: Full XOR did NOT match. ASCON's sponge state successfully diverged after the first difference.")

        # ---------------------------------------------------------
        print("\n[Test 4b] True ASCON Nonce Reuse Leak (Sponge Construction Rate)")
        # In ASCON-128, the block size (rate) is 8 bytes. 
        # The XOR leak only happens perfectly on the first block before the internal state diverges.
        BLOCK_SIZE = 8
        
        xor_ct_block = bytes(a ^ b for a, b in zip(ct_a[:BLOCK_SIZE], ct_b[:BLOCK_SIZE]))
        xor_pt_block = bytes(a ^ b for a, b in zip(waveform_a[:BLOCK_SIZE], waveform_b[:BLOCK_SIZE]))
        
        if xor_ct_block == xor_pt_block:
            print(f"⚠️  DANGER PROVEN: First {BLOCK_SIZE} bytes of ct_a XOR ct_b perfectly matches plaintext_a XOR plaintext_b")
            print("✅ PASS: Sponge nonce reuse vulnerability successfully demonstrated")
        else:
            print("❌ FAIL: Block XOR properties did not match")
            
   
    print("\n" + "="*50)

if __name__ == "__main__":
    run_security_tests()
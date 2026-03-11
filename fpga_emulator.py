#!/usr/bin/env python3
"""
FPGA Emulator for IACQ course.
This emulator simulates the FPGA's UART behavior for home development and testing.
Author: Raphael Viera (raphael.viera@emse.fr - raphaelviera.myresearch.ac)

The emulator implements the same command protocol as the real FPGA:
- K (0x4B): Receive encryption key (16 bytes)
- N (0x4E): Receive nonce (16 bytes)
- A (0x41): Receive associated data (10 bytes with padding)
- W (0x57): Receive ECG waveform (184 bytes with padding)
- G (0x47): Start encryption
- T (0x54): Return authentication tag (16 bytes)
- C (0x43): Return ciphertext (184 bytes)

Usage:
    The emulator provides a serial-port-like interface. Use it as a drop-in
    replacement for serial.Serial when developing at home.

    Example:
        emulator = FPGAEmulator()
        emulator.open()

        # Send key command
        emulator.write(bytes([0x4B]) + key)  # K command
        response = emulator.readline()  # Should be b"OK\\n"

        # ... continue with other commands ...

        emulator.close()

Author: Course Material for Interface et Acquisition
"""

import time
import logging
from typing import Optional
from collections import deque

# Import ASCON from reference implementation
import ascon_pcsn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fpga_emulator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('FPGAEmulator')


def _ascon_encrypt_quiet(key: bytes, nonce: bytes, associateddata: bytes, plaintext: bytes) -> bytes:
    """Call ascon_pcsn.ascon_encrypt with debug output disabled."""
    # Save current debug settings
    old_debug = ascon_pcsn.debug
    old_debugperm = ascon_pcsn.debugpermutation
    old_debugtrans = ascon_pcsn.debugtransformation

    # Disable debug output
    ascon_pcsn.debug = False
    ascon_pcsn.debugpermutation = False
    ascon_pcsn.debugtransformation = False

    try:
        return ascon_pcsn.ascon_encrypt(key, nonce, associateddata, plaintext, "Ascon-128")
    finally:
        # Restore debug settings
        ascon_pcsn.debug = old_debug
        ascon_pcsn.debugpermutation = old_debugperm
        ascon_pcsn.debugtransformation = old_debugtrans


# =============================================================================
# FPGA Emulator Class
# =============================================================================

class FPGAEmulator:
    """
    Emulates the FPGA UART interface for the Secure ECG Acquisition course.

    This class provides a serial-port-like interface that behaves identically
    to the real FPGA, allowing students to develop and test their code at home.

    The interface mimics PySerial's Serial class, so you can use it as a
    drop-in replacement when testing without hardware.

    Attributes:
        port (str): Virtual port name (for compatibility)
        baud_rate (int): Baud rate (for compatibility, not used)
        timeout (float): Read timeout in seconds
        is_open (bool): Whether the connection is open

    Example:
        >>> emulator = FPGAEmulator(port="VIRTUAL", timeout=1.0)
        >>> emulator.open()
        >>>
        >>> # Send a command (e.g., key)
        >>> key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
        >>> emulator.write(bytes([0x4B]) + key)  # K command
        >>> response = emulator.readline()
        >>> print(response)  # b'OK\\n'
        >>>
        >>> emulator.close()
    """

    # Command codes
    CMD_KEY = 0x4B           # 'K'
    CMD_NONCE = 0x4E         # 'N'
    CMD_ASSOC_DATA = 0x41    # 'A'
    CMD_WAVEFORM = 0x57      # 'W'
    CMD_GO = 0x47            # 'G'
    CMD_GET_TAG = 0x54       # 'T'
    CMD_GET_CIPHER = 0x43    # 'C'

    # Expected data lengths
    KEY_LENGTH = 16
    NONCE_LENGTH = 16
    ASSOC_DATA_LENGTH = 10   # 8 bytes + 2 padding
    WAVEFORM_LENGTH = 184    # 181 bytes + 3 padding
    TAG_LENGTH = 16

    def __init__(self, port: str = "VIRTUAL", baud_rate: int = 115200,
                 timeout: float = 1.0, simulate_delays: bool = True):
        """
        Initialize the FPGA emulator.

        Args:
            port: Virtual port name (for compatibility with real FPGA class)
            baud_rate: Baud rate (for compatibility, not actually used)
            timeout: Read timeout in seconds
            simulate_delays: If True, add realistic delays to simulate hardware
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.simulate_delays = simulate_delays

        self.is_open = False
        self._read_buffer = deque()

        # Encryption state
        self._key: Optional[bytes] = None
        self._nonce: Optional[bytes] = None
        self._associated_data: Optional[bytes] = None
        self._plaintext: Optional[bytes] = None
        self._ciphertext: Optional[bytes] = None
        self._tag: Optional[bytes] = None
        self._encryption_done = False

        logger.info(f"FPGAEmulator initialized (port={port}, baud_rate={baud_rate})")

    def open(self) -> None:
        """Open the virtual connection."""
        if self.is_open:
            logger.warning("Connection already open")
            return

        self.is_open = True
        self._reset_state()
        logger.info("FPGAEmulator connection opened")

        if self.simulate_delays:
            time.sleep(0.1)

    def close(self) -> None:
        """Close the virtual connection."""
        if not self.is_open:
            logger.warning("Connection already closed")
            return

        self.is_open = False
        self._reset_state()
        logger.info("FPGAEmulator connection closed")

    def _reset_state(self) -> None:
        """Reset internal encryption state."""
        self._key = None
        self._nonce = None
        self._associated_data = None
        self._plaintext = None
        self._ciphertext = None
        self._tag = None
        self._encryption_done = False
        self._read_buffer.clear()

    def write(self, data: bytes) -> int:
        """
        Write data to the emulator (send command to virtual FPGA).

        Args:
            data: Bytes to send (command + optional payload)

        Returns:
            Number of bytes written
        """
        if not self.is_open:
            raise IOError("Connection not open")

        if len(data) == 0:
            return 0

        logger.debug(f"Write: {len(data)} bytes")

        command = data[0]
        payload = data[1:] if len(data) > 1 else b""

        response = self._process_command(command, payload)

        for byte in response:
            self._read_buffer.append(byte)

        if self.simulate_delays:
            time.sleep(0.01)

        return len(data)

    def read(self, size: int = 1) -> bytes:
        """
        Read bytes from the emulator.

        Args:
            size: Number of bytes to read

        Returns:
            Bytes read from buffer
        """
        if not self.is_open:
            raise IOError("Connection not open")

        result = bytearray()
        start_time = time.time()

        while len(result) < size:
            if self._read_buffer:
                result.append(self._read_buffer.popleft())
            elif time.time() - start_time > self.timeout:
                break
            else:
                time.sleep(0.001)

        return bytes(result)

    def readline(self) -> bytes:
        """
        Read until newline character.

        Returns:
            Bytes read including the newline
        """
        if not self.is_open:
            raise IOError("Connection not open")

        result = bytearray()
        start_time = time.time()

        while True:
            if self._read_buffer:
                byte = self._read_buffer.popleft()
                result.append(byte)
                if byte == ord('\n'):
                    break
            elif time.time() - start_time > self.timeout:
                break
            else:
                time.sleep(0.001)

        return bytes(result)

    def read_all(self) -> bytes:
        """
        Read all available bytes from buffer.

        Returns:
            All bytes currently in the buffer
        """
        if not self.is_open:
            raise IOError("Connection not open")

        result = bytes(self._read_buffer)
        self._read_buffer.clear()
        return result

    @property
    def in_waiting(self) -> int:
        """Return number of bytes waiting in read buffer."""
        return len(self._read_buffer)

    def _process_command(self, command: int, payload: bytes) -> bytes:
        """Process a command and return the response."""
        try:
            if command == self.CMD_KEY:
                return self._handle_key(payload)
            elif command == self.CMD_NONCE:
                return self._handle_nonce(payload)
            elif command == self.CMD_ASSOC_DATA:
                return self._handle_associated_data(payload)
            elif command == self.CMD_WAVEFORM:
                return self._handle_waveform(payload)
            elif command == self.CMD_GO:
                return self._handle_go()
            elif command == self.CMD_GET_TAG:
                return self._handle_get_tag()
            elif command == self.CMD_GET_CIPHER:
                return self._handle_get_ciphertext()
            else:
                logger.warning(f"Unknown command: 0x{command:02X}")
                return b"ERROR\n"
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return b"ERROR\n"

    def _handle_key(self, payload: bytes) -> bytes:
        """Handle key command (K)."""
        if len(payload) != self.KEY_LENGTH:
            logger.error(f"Invalid key length: {len(payload)}")
            return b"ERROR\n"

        self._key = payload
        self._encryption_done = False
        logger.info(f"Key received: {payload.hex()}")
        return b"OK\n"

    def _handle_nonce(self, payload: bytes) -> bytes:
        """Handle nonce command (N)."""
        if len(payload) != self.NONCE_LENGTH:
            logger.error(f"Invalid nonce length: {len(payload)}")
            return b"ERROR\n"

        self._nonce = payload
        self._encryption_done = False
        logger.info(f"Nonce received: {payload.hex()}")
        return b"OK\n"

    def _handle_associated_data(self, payload: bytes) -> bytes:
        """Handle associated data command (A)."""
        if len(payload) != self.ASSOC_DATA_LENGTH:
            logger.error(f"Invalid AD length: {len(payload)}")
            return b"ERROR\n"

        # Remove padding to get original AD
        # Format: [AD padded to 8 bytes with zeros] + [0x80 0x00]
        # We need to find 0x80, take data before it, and strip trailing zeros
        try:
            padding_start = payload.index(0x80)
            self._associated_data = payload[:padding_start].rstrip(b'\x00')
        except ValueError:
            self._associated_data = payload.rstrip(b'\x00')

        self._encryption_done = False
        logger.info(f"Associated data received: {self._associated_data}")
        return b"OK\n"

    def _handle_waveform(self, payload: bytes) -> bytes:
        """Handle waveform command (W)."""
        if len(payload) != self.WAVEFORM_LENGTH:
            logger.error(f"Invalid waveform length: {len(payload)}")
            return b"ERROR\n"

        # Remove padding (last 3 bytes)
        self._plaintext = payload[:181]
        self._encryption_done = False
        logger.info(f"Waveform received: {len(self._plaintext)} bytes")
        return b"OK\n"

    def _handle_go(self) -> bytes:
        """Handle go command (G) - start encryption."""
        if self._key is None:
            logger.error("Cannot encrypt: key not set")
            return b"ERROR\n"
        if self._nonce is None:
            logger.error("Cannot encrypt: nonce not set")
            return b"ERROR\n"
        if self._associated_data is None:
            logger.error("Cannot encrypt: associated data not set")
            return b"ERROR\n"
        if self._plaintext is None:
            logger.error("Cannot encrypt: waveform not set")
            return b"ERROR\n"

        logger.info("Starting encryption...")

        if self.simulate_delays:
            time.sleep(0.05)

        # Perform ASCON encryption using ascon_pcsn
        result = _ascon_encrypt_quiet(
            self._key,
            self._nonce,
            self._associated_data,
            self._plaintext
        )

        self._ciphertext = result[:-16]
        self._tag = result[-16:]
        self._encryption_done = True

        logger.info(f"Encryption complete. Tag: {self._tag.hex()}")
        return b"OK\n"

    def _handle_get_tag(self) -> bytes:
        """Handle get tag command (T)."""
        if not self._encryption_done:
            logger.error("Cannot get tag: encryption not performed")
            return b"ERROR\n"

        logger.info(f"Returning tag: {self._tag.hex()}")
        return self._tag + b"OK\n"

    def _handle_get_ciphertext(self) -> bytes:
        """Handle get ciphertext command (C)."""
        if not self._encryption_done:
            logger.error("Cannot get ciphertext: encryption not performed")
            return b"ERROR\n"

        # Add padding to match expected length (184 bytes)
        padded_ciphertext = self._ciphertext + bytes([0x80, 0x00, 0x00])
        logger.info(f"Returning ciphertext: {len(padded_ciphertext)} bytes")
        return padded_ciphertext + b"OK\n"


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    print("FPGAEmulator - Quick Connection Test")
    print("=" * 40)

    # Create and open emulator
    emulator = FPGAEmulator()
    emulator.open()
    print("Emulator opened successfully")

    # Test sending a key
    test_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
    emulator.write(bytes([0x4B]) + test_key)  # K command
    response = emulator.readline()
    print(f"Sent key, response: {response}")

    emulator.close()
    print("Emulator closed")
    print("\nEmulator is working! Now build your FPGA class.")

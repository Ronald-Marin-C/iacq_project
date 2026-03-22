from exceptions import FPGAConnectionError, FPGATimeoutError, FPGAValidationError, FPGAProtocolError, FPGAAuthenticationError
from ascon_pcsn import ascon_decrypt
from fpga_emulator import FPGAEmulator
import serial
import logging
import time

# --- Exclusive Logging Configuration for IACQ ---
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)  # Debug
logger.setLevel(logging.INFO)  # Performance
logger.propagate = False        

# Setting of handlers to avoid duplicate logs if this module is imported multiple times
if not logger.handlers:
    file_handler = logging.FileHandler('fpga_communication.log')
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

class IACQ:
    def __init__(self, port, baud_rate=115200, timeout=1, emulator=False, max_retries=3):
        """Initialize the IACQ connection settings.

        Args:
            port (str): Serial port identifier (e.g., 'COM3' or '/dev/ttyUSB0').
            baud_rate (int, optional): Communication baud rate. Defaults to 115200.
            timeout (int, optional): Read/write timeout in seconds. Defaults to 1.
            emulator (bool, optional): Flag to use the FPGA emulator instead of physical hardware. Defaults to False.

        Example:
            >>> fpga = IACQ('COM3', emulator=True)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.use_emulator = emulator
        self.max_retries = max_retries
        self.connection = None

    def open_connection(self):
        """Open the connection to the FPGA or emulator.

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
        """
        if self.use_emulator:
            self.connection = FPGAEmulator()
            self.connection.open()
            logger.info("Connection opened (Emulator)")  # Tarea 2: Log INFO
        else:
            self.connection = self._open_serial()
            if self.connection:
                logger.info(f"Connection opened on {self.port}")  # Tarea 2: Log INFO
    
    def _open_serial(self):
        """Open the physical serial connection.

        Returns:
            serial.Serial | None: The serial connection object, or None if the connection fails.

        Example:
            >>> fpga = IACQ('COM3')
            >>> conn = fpga._open_serial()
        """
        try:
            serialConnection = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            return serialConnection
        except serial.SerialException as e:
            logger.error(f"Error opening serial port: {e}")  # Tarea 5: Log ERROR
            return None
        
    def close_connection(self):  
        """Close the active connection to the FPGA or emulator.

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
            >>> fpga.close_connection()
        """
        if self.connection:
            self.connection.close()
            logger.info("Connection closed")  # Tarea 2: Log INFO


    def send_command(self, command):
        """Send a raw command to the connected FPGA or emulator.

        Args:
            command (bytes | str): The command data to transmit.

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
            >>> fpga.send_command(b'\\x4B' + b'\\x00'*16)
        """
        if self.connection is None:
            logger.error("Connection not open. Call open_connection() first.")  # Tarea 5: Log ERROR
            return        
        
        # Tarea 3: Log DEBUG (excluyendo secretos)
        # Como estás enviando el comando y la llave juntos, extraemos solo la letra del comando para el log
        if isinstance(command, bytes):
            cmd_letter = chr(command[0])
            logger.debug(f"TX: Command '{cmd_letter}' sent ({len(command)} bytes total)") 
            self.connection.write(command)
        else:
            logger.debug(f"TX: {command} ({len(command)} bytes)")
            self.connection.write(command.encode())


    def send_key(self, key: bytes) -> None:
        """Send the encryption key to the FPGA (Command 'K').

        Args:
            key (bytes): 16-byte ASCON-128 encryption key.

        Raises:
            FPGAValidationError: If key is not bytes type or not exactly 16 bytes.

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
            >>> fpga.send_key(bytes.fromhex('8A55114D...'))
        """
        if not isinstance(key, bytes):
            raise FPGAValidationError(f"Key must be bytes, got {type(key).__name__}")
        if len(key) != 16:
            raise FPGAValidationError(f"Key must be exactly 16 bytes, got {len(key)}")
            
        self.send_command(bytes([0x4B]) + key)
        resp = self.read_response()
        logger.debug(f"Key set response: {resp}")

    def send_nonce(self, nonce: bytes)-> None:
        """Send the cryptographic nonce to the FPGA (Command 'N').

        Args:
            nonce (bytes): 16-byte nonce.

        Raises:
            FPGAValidationError: If nonce is not bytes type or not exactly 16 bytes.

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
            >>> fpga.send_nonce(bytes.fromhex('01234567...'))
        """
        if not isinstance(nonce, bytes):
            raise FPGAValidationError(f"Nonce must be bytes, got {type(nonce).__name__}")
        if len(nonce) != 16:
            raise FPGAValidationError(f"Nonce must be exactly 16 bytes, got {len(nonce)}")
            
        self.send_command(bytes([0x4E]) + nonce)
        resp = self.read_response()
        logger.debug(f"Nonce set response: {resp}")

    def send_associated_data(self, ad: bytes):
        """Send Associated Data to the FPGA (Command 'A').
        
        Pads the input internally to 10 bytes: [AD padded to 8 bytes] + [0x80] + [0x00].

        Args:
            ad (bytes): Associated data, maximum of 8 bytes.

        Raises:
            FPGAValidationError: If Associated Data is not bytes type or exceeds 8 bytes.

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
            >>> fpga.send_associated_data(b'Header12')
        """
        if not isinstance(ad, bytes):
            raise FPGAValidationError(f"Associated Data must be bytes, got {type(ad).__name__}")
        if len(ad) > 8:
            raise FPGAValidationError(f"Associated Data cannot exceed 8 bytes, got {len(ad)}")
            
        # Rellenar con ceros hasta 8 bytes, luego agregar el padding final
        padded_ad = ad.ljust(8, b'\x00') + b'\x80\x00'
        
        self.send_command(bytes([0x41]) + padded_ad)
        resp = self.read_response()
        logger.debug(f"AD set response: {resp}")

    def send_waveform_to_fpga(self, waveform: bytes):
            """Send 181-byte waveform with 184-byte padding (Command 'W').
            
            Pads the input internally to 184 bytes: [181 bytes data] + [0x80] + [0x00] + [0x00].

            Args:
                waveform (bytes): Exactly 181 bytes of ECG waveform data.

            Raises:
                FPGAValidationError: If waveform is not bytes type or not exactly 181 bytes.

            Example:
                >>> fpga = IACQ('COM3')
                >>> fpga.open_connection()
                >>> fpga.send_waveform_to_fpga(b'\\x00' * 181)
            """
            if not isinstance(waveform, bytes):
                raise FPGAValidationError(f"Waveform must be bytes, got {type(waveform).__name__}")
            if len(waveform) != 181:
                raise FPGAValidationError(f"Waveform must be exactly 181 bytes, got {len(waveform)}")
            
            padded_waveform = waveform + b'\x80\x00\x00'
            
            self.send_command(bytes([0x57]) + padded_waveform)
            resp = self.read_response()
            logger.debug(f"Waveform sent response: {resp}")
        

    def start_encryption(self) -> None:
        """Trigger the ASCON encryption process on the FPGA (Command 'G').

        Example:
            >>> fpga = IACQ('COM3')
            >>> fpga.open_connection()
            >>> # ... send key, nonce, ad, waveform ...
            >>> fpga.start_encryption()
        """
        self.send_command(bytes([0x47]))
        resp = self.read_response()
        logger.debug(f"Encryption trigger response: {resp}")

    def get_tag(self) -> bytes:
        """Retrieve the 16-byte authentication tag from the FPGA (Command 'T').

        Returns:
            bytes: The 16-byte ASCON authentication tag.

        Example:
            >>> tag = fpga.get_tag()
            >>> print(tag.hex().upper())
        """
        self.send_command(bytes([0x54]))
        tag = self.read_response(size=16) # Read the 16 bytes of the tag
        ok_status = self.read_response() # Read the trailing 'OK\n'
        return tag

    def get_ciphertext(self) -> bytes:
        """Retrieve the ciphertext and strip internal padding (Command 'C').
        
        Reads 184 bytes from the FPGA (181 bytes of encrypted data + 3 bytes 
        of padding) and returns only the original 181-byte payload.

        Returns:
            bytes: The decrypted 181-byte ciphertext.

        Example:
            >>> ciphertext = fpga.get_ciphertext()
            >>> len(ciphertext)
            181
        """
        self.send_command(bytes([0x43]))
        # Read the 184 bytes (181 ciphertext + 3 padding)
        padded_ciphertext = self.read_response(size=184)
        ok_status = self.read_response() # Read the trailing 'OK\n'
        
        # Strip the last 3 bytes of padding and return
        return padded_ciphertext[:181]
    
    # ==========================================
    # HIGH-LEVEL PIPELINE METHODS (ACTIVITY 2.4)
    # ==========================================

    def encrypt_on_fpga(self, waveform: bytes, key: bytes, nonce: bytes, associated_data: bytes) -> tuple[bytes, bytes]:
        """Execute the full encryption sequence on the FPGA.

        Args:
            waveform (bytes): 181-byte ECG waveform data.
            key (bytes): 16-byte ASCON-128 encryption key.
            nonce (bytes): 16-byte nonce.
            associated_data (bytes): Up to 8 bytes of associated data.

        Returns:
            tuple[bytes, bytes]: A tuple containing (ciphertext, tag).
        """
        self.send_key(key)
        self.send_nonce(nonce)
        self.send_associated_data(associated_data)
        self.send_waveform_to_fpga(waveform)
        self.start_encryption()
        
        tag = self.get_tag()
        ciphertext = self.get_ciphertext()
        
        return ciphertext, tag

    def decrypt_waveform(self, ciphertext: bytes, tag: bytes, key: bytes, nonce: bytes, associated_data: bytes) -> bytes:
        """Decrypt ciphertext received from the FPGA using the Python ASCON library.

        Args:
            ciphertext (bytes): 181-byte encrypted payload.
            tag (bytes): 16-byte authentication tag.
            key (bytes): 16-byte encryption key.
            nonce (bytes): 16-byte nonce.
            associated_data (bytes): Associated data used during encryption.

        Returns:
            bytes: The decrypted 181-byte plaintext waveform.

        Raises:
            FPGAAuthenticationError: If the tag verification fails.
        """
        # The reference ascon_pcsn library expects the tag to be appended to the ciphertext
        combined_data = ciphertext + tag
        
        decrypted = ascon_decrypt(key, nonce, associated_data, combined_data)
        
        if decrypted is None:
            raise FPGAAuthenticationError("Authentication failed: Ciphertext or Tag has been tampered with.")
            
        return decrypted
    
    # ==========================================
    # CHANGE METHODS (ACTIVITY 2.5)
    # ==========================================
    def reconnect(self, delay: float = 1.0) -> None:
        """Attempt to recover a dropped connection (Task 5).
        
        Closes the current connection, waits briefly, and attempts to reopen.
        Raises FPGAConnectionError if all retries fail.
        """
        logger.warning("Attempting to recover connection to FPGA...")
        self.close_connection()
        
        for attempt in range(self.max_retries):
            time.sleep(delay)
            try:
                self.open_connection()
                if self.connection:
                    logger.info("Connection recovered successfully.")
                    return
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")
                
        raise FPGAConnectionError(f"Failed to reconnect after {self.max_retries} attempts.")

    def read_response(self, size: int = None) -> bytes:
        """Read response from device with retry logic for timeouts (Task 3)."""
        if self.connection is None:
            raise FPGAConnectionError("Connection not open.")
        
        for attempt in range(self.max_retries):
            if size:
                response = self.connection.read(size)
            else:
                response = self.connection.readline()
                
            if response:
                logger.debug(f"RX: {response}")
                return response
                
            logger.warning(f"Timeout reading from device (Attempt {attempt + 1}/{self.max_retries}). Retrying...")
            time.sleep(0.5)
            
        raise FPGATimeoutError(f"Exhausted {self.max_retries} retries. No response received from device.")

    def _verify_ok_response(self, context: str):
        """Verify the 'OK' acknowledgment, handling unexpected formats (Task 4)."""
        response = self.read_response()
        
        try:
            resp_str = response.decode('utf-8').strip()
            if resp_str == "OK":
                return # Validation passed
        except UnicodeDecodeError:
            pass # It's not a valid string, so it's definitely not "OK"
            
        # If we reach here, the response was not "OK"
        raise FPGAProtocolError(f"Unexpected format setting {context}. Expected 'OK', got raw hex: {response.hex()}")

    def __enter__(self):
        """Context manager entry point. Opens the connection automatically.

        Returns:
            IACQ: The current instance of the class.

        Example:
            >>> with IACQ('COM3') as fpga:
            ...     fpga.send_key(b'\\x00'*16)
        """
        self.open_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point. Closes the connection automatically.

        Args:
            exc_type: The exception type, if an exception was raised.
            exc_val: The exception value, if an exception was raised.
            exc_tb: The traceback, if an exception was raised.

        Returns:
            bool: False to propagate any exceptions raised within the context block.
        """
        self.close_connection() 
        return False
        
if __name__ == "__main__":
    logger.info("--- Starting Activity 2.5: Error Handling & Edge Cases ---")
    
    with IACQ(port='COM8', emulator=True) as fpga:
        try:
            # 1. Setup Parameters
            correct_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
            wrong_key = bytes([0] * 16) # 16 zero bytes (The "Hacker" key)
            test_nonce = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
            test_ad = b"A to B"
            
            # Load waveform
            with open("data/xNorm.csv", "r") as f:
                original_waveform = bytes.fromhex(f.readline().strip())
            
            # 2. Encrypt normally with CORRECT key
            logger.info("Encrypting with CORRECT key...")
            ciphertext, tag = fpga.encrypt_on_fpga(original_waveform, correct_key, test_nonce, test_ad)
            
            # 3. Decrypt with WRONG key (Task 2)
            logger.info("Attempting to decrypt with WRONG key...")
            decrypted_waveform = fpga.decrypt_waveform(ciphertext, tag, wrong_key, test_nonce, test_ad)
            
            # If we reach here, ASCON is broken!
            logger.error("CRITICAL FAILURE: Decryption succeeded with the wrong key!")

        except FPGAAuthenticationError as e:
            logger.info(f"[SUCCESS] Wrong Key Test passed. Caught expected error: {e}")
        except Exception as e:
            logger.error(f"Test Failed with unexpected error: {e}")
            
        # 4. Connection Recovery Test (Task 5)
        logger.info("--- Testing Connection Recovery ---")
        try:
            fpga.reconnect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
    logger.info("--- Starting AEAD Security Failure Test ---")
    
    with IACQ(port='COM8', emulator=True) as fpga:
        try:
            # 1. Setup Parameters
            test_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
            test_nonce = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
            test_ad = b"A to B"
            
            # Load waveform
            with open("data/xNorm.csv", "r") as f:
                original_waveform = bytes.fromhex(f.readline().strip())
            
            # 2. High-Level Encryption
            ciphertext, tag = fpga.encrypt_on_fpga(original_waveform, test_key, test_nonce, test_ad)
            
            # ======================================================
            # 3. HACKER SIMULATION: Tamper with the Ciphertext
            # ======================================================
            logger.info(">>> MALICIOUS ACTOR: Tampering with 1 byte of the ciphertext...")
            tampered_ciphertext = bytearray(ciphertext)
            
            # Let's corrupt just the very first byte by flipping its bits (XOR 0xFF)
            tampered_ciphertext[0] ^= 0xFF 
            tampered_ciphertext = bytes(tampered_ciphertext)
            
            # ======================================================
            
            # 4. High-Level Decryption (Software) - THIS SHOULD FAIL!
            logger.info("Decrypting tampered data in Python...")
            decrypted_waveform = fpga.decrypt_waveform(tampered_ciphertext, tag, test_key, test_nonce, test_ad)
            
            # If we reach here, ASCON failed to protect us
            logger.error("CRITICAL SECURITY FAILURE: ASCON decrypted tampered data!")

        except FPGAAuthenticationError as e:
            logger.info(f">>> [SUCCESSFUL DEFENSE] Security caught the tampering: {e}")
        except Exception as e:
            logger.error(f"Test Failed with unexpected error: {e}")
    logger.info("--- Starting End-to-End Cross-Platform Validation ---")
    
    with IACQ(port='COM8', emulator=True) as fpga:
        try:
            # 1. Setup Parameters
            test_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
            test_nonce = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
            test_ad = b"A to B"
            
            # 2. Load the first waveform from xNorm.csv
            csv_path = "data/xNorm.csv"
            with open(csv_path, "r") as f:
                first_line = f.readline().strip()
                original_waveform = bytes.fromhex(first_line)
            
            logger.info(f"Loaded original waveform: {len(original_waveform)} bytes")
            
            # 3. High-Level Encryption (Hardware/Emulator)
            logger.info("Encrypting on FPGA...")
            ciphertext, tag = fpga.encrypt_on_fpga(original_waveform, test_key, test_nonce, test_ad)
            
            # 4. High-Level Decryption (Software)
            logger.info("Decrypting in Python...")
            decrypted_waveform = fpga.decrypt_waveform(ciphertext, tag, test_key, test_nonce, test_ad)
            
            # 5. Validate Identity
            if original_waveform == decrypted_waveform:
                logger.info("[SUCCESS] Cross-platform validation passed! Decrypted data is byte-for-byte identical.")
            else:
                logger.error("[ERROR] Validation failed. Data mismatch.")
                
        except FPGAAuthenticationError as e:
            logger.error(f"[SECURITY ALERT] {e}")
        except Exception as e:
            logger.error(f"Test Failed: {e}")
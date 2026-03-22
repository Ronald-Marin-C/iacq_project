from exceptions import FPGAConnectionError, FPGATimeoutError, FPGAValidationError, FPGAProtocolError
from fpga_emulator import FPGAEmulator
import serial
import logging

# --- Exclusive Logging Configuration for IACQ ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  
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
    def __init__(self, port, baud_rate=115200, timeout=1, emulator=False):
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

    def read_response(self, size: int = None) -> bytes:
        """Read a line of response from the FPGA or emulator.

        Args:
            size: If provided, read exactly 'size' bytes. Otherwise, read a line.

        Returns:
            bytes | None: The decoded response bytes, or None if the connection is not open.

        Example:
            >>> fpga = IACQ('COM3')
            >>> response = fpga.read_response()
            >>> print(response)
            'OK'
        """
        if self.connection is None:
            logger.error("Connection not open. Call open_connection() first.") 
            return None
        
        if size:
            # Read exact number of bytes
            response = self.connection.read(size)
        else:
            # Read until newline
            response = self.connection.readline()
        
        if not response:
            logger.warning("Timeout: No response received from device.")
        else:
            logger.debug(f"RX: {response}")  # Tarea 3: Log DEBUG para datos recibidos
            
        return response

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
        

    def _verify_ok_response(self, context: str):
        """Verify that the FPGA responded with 'OK'.

        Args:
            context (str): Description of the command sent, used for error reporting.

        Raises:
            FPGAProtocolError: If the response from the FPGA is not 'OK'.

        Example:
            >>> self._verify_ok_response("Key")
        """
        response = self.read_response()
        if response != "OK":
            raise FPGAProtocolError(f"Failed to set {context}. Expected 'OK', got: '{response}'")   
        
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
    logger.info("--- Starting Full FPGA Protocol Test ---")
    
    with IACQ(port='COM8', emulator=True) as fpga:
        try:
            # 1. Setup Test Data
            test_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
            test_nonce = bytes.fromhex("4ED0EC0B98C529B7C8CDDF37BCD0284A")
            test_ad = b"A to B"
            dummy_waveform = bytes([128] * 181) # 181 bytes of dummy ECG data (flatline)
            
            # 2. Execute Encryption Pipeline
            logger.info("Step 1: Sending Key...")
            fpga.send_key(test_key)
            
            logger.info("Step 2: Sending Nonce...")
            fpga.send_nonce(test_nonce)
            
            logger.info("Step 3: Sending Associated Data...")
            fpga.send_associated_data(test_ad)
            
            logger.info("Step 4: Sending Waveform...")
            fpga.send_waveform_to_fpga(dummy_waveform)
            
            logger.info("Step 5: Starting Encryption...")
            fpga.start_encryption()
            
            logger.info("Step 6: Retrieving Tag...")
            tag = fpga.get_tag()
            logger.info(f"[SUCCESS] Retrieved Tag: {tag.hex().upper()}")
            
            logger.info("Step 7: Retrieving Ciphertext...")
            ciphertext = fpga.get_ciphertext()
            logger.info(f"[SUCCESS] Retrieved Ciphertext ({len(ciphertext)} bytes). First 10 bytes: {ciphertext[:10].hex().upper()}")
            
            logger.info("--- Protocol Test Completed Successfully! ---")
            
        except Exception as e:
            logger.error(f"Pipeline Test Failed: {e}")
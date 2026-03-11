from exceptions import FPGAConnectionError, FPGATimeoutError, FPGAValidationError, FPGAProtocolError
from fpga_emulator import FPGAEmulator
import serial
import logging

# --- Configuración Exclusiva del Logging para IACQ ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  
logger.propagate = False        

# Configuramos nuestros propios Handlers si no existen
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
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.use_emulator = emulator
        self.connection = None

    def open_connection(self):
        if self.use_emulator:
            self.connection = FPGAEmulator()
            self.connection.open()
            logger.info("Connection opened (Emulator)")  # Tarea 2: Log INFO
        else:
            self.connection = self._open_serial()
            if self.connection:
                logger.info(f"Connection opened on {self.port}")  # Tarea 2: Log INFO
    
    def _open_serial(self):
        try:
            serialConnection = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            return serialConnection
        except serial.SerialException as e:
            logger.error(f"Error opening serial port: {e}")  # Tarea 5: Log ERROR
            return None
        
    def close_connection(self):  
        if self.connection:
            self.connection.close()
            logger.info("Connection closed")  # Tarea 2: Log INFO

    def send_command(self, command):
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

    def read_response(self):   
        if self.connection is None:
            logger.error("Connection not open. Call open_connection() first.")  # Tarea 5: Log ERROR
            return None
        
        response = self.connection.readline().decode().strip()
        
        # Tarea 4: Log WARNING para timeouts (si no llega nada en el tiempo establecido)
        if not response:
            logger.warning("Timeout: No response received from device.")
        else:
            logger.debug(f"RX: {response}")  # Tarea 3: Log DEBUG para datos recibidos
            
        return response

    def send_key(self, key: bytes):
        """
        Send the 16-byte encryption key (Command 'K').
        Raises FPGAValidationError if input is invalid.
        """
        if not isinstance(key, bytes):
            raise FPGAValidationError(f"Key must be bytes, got {type(key).__name__}")
        if len(key) != 16:
            raise FPGAValidationError(f"Key must be exactly 16 bytes, got {len(key)}")
            
        self.send_command(bytes([0x4B]) + key)
        self._verify_ok_response("Key")

    def send_nonce(self, nonce: bytes):
        """
        Send the 16-byte nonce (Command 'N').
        Raises FPGAValidationError if input is invalid.
        """
        if not isinstance(nonce, bytes):
            raise FPGAValidationError(f"Nonce must be bytes, got {type(nonce).__name__}")
        if len(nonce) != 16:
            raise FPGAValidationError(f"Nonce must be exactly 16 bytes, got {len(nonce)}")
            
        self.send_command(bytes([0x4E]) + nonce)
        self._verify_ok_response("Nonce")

    def send_ad(self, ad: bytes):
        """
        Send Associated Data (Command 'A'). Max 8 bytes.
        Pads internally to 10 bytes: [AD padded to 8 bytes] + [0x80] + [0x00].
        """
        if not isinstance(ad, bytes):
            raise FPGAValidationError(f"Associated Data must be bytes, got {type(ad).__name__}")
        if len(ad) > 8:
            raise FPGAValidationError(f"Associated Data cannot exceed 8 bytes, got {len(ad)}")
            
        # Rellenar con ceros hasta 8 bytes, luego agregar el padding final
        padded_ad = ad.ljust(8, b'\x00') + b'\x80\x00'
        
        self.send_command(bytes([0x41]) + padded_ad)
        self._verify_ok_response("Associated Data")

    def send_waveform(self, waveform: bytes):
        """
        Send ECG Waveform (Command 'W'). Exactly 181 bytes.
        Pads internally to 184 bytes: [181 bytes data] + [0x80] + [0x00] + [0x00].
        """
        if not isinstance(waveform, bytes):
            raise FPGAValidationError(f"Waveform must be bytes, got {type(waveform).__name__}")
        if len(waveform) != 181:
            raise FPGAValidationError(f"Waveform must be exactly 181 bytes, got {len(waveform)}")
            
        padded_waveform = waveform + b'\x80\x00\x00'
        
        self.send_command(bytes([0x57]) + padded_waveform)
        self._verify_ok_response("Waveform")

    def _verify_ok_response(self, context: str):
        """Helper para verificar que la FPGA respondió con 'OK'."""
        response = self.read_response()
        if response != "OK":
            raise FPGAProtocolError(f"Failed to set {context}. Expected 'OK', got: '{response}'")   

    def __enter__(self):
        self.open_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection() 
        return False
    
if __name__ == "__main__":
    with IACQ(port='COM8', emulator=True) as iacq:
        
        logger.info("--- Iniciando pruebas de validación ---")
        
        # 1. Prueba Exitosa (16 bytes)
        try:
            valid_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
            iacq.send_key(valid_key)
            logger.info("Prueba de llave válida: PASÓ")
        except Exception as e:
            logger.error(f"Error inesperado: {e}")

        # 2. Prueba de Falla Rápida: Tipo incorrecto
        try:
            iacq.send_key("esto es un string, no bytes")
        except FPGAValidationError as e:
            logger.info(f"Falla detectada correctamente (Tipo): {e}")

        # 3. Prueba de Falla Rápida: Longitud incorrecta (15 bytes)
        try:
            invalid_length_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAA") # Falta 1 byte
            iacq.send_key(invalid_length_key)
        except FPGAValidationError as e:
            logger.info(f"Falla detectada correctamente (Longitud): {e}")
from fpga_emulator import FPGAEmulator
import serial

class IACQ:
    def __init__(self, port, baud_rate=115200, timeout=1, emulator=False):
        """
        Initialize IACQ communication interface.

        Args:
            port: Serial port (e.g., 'COM3' or '/dev/ttyUSB0')
            baud_rate: Communication speed (default 115200)
            timeout: Read timeout in seconds
            emulator: If True, use software emulator instead of hardware
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.use_emulator = emulator
        self.connection = None

    def open_connection(self):
            """
            Open the communication connection to the IACQ device or emulator.
            """
            if self.use_emulator:
                self.connection = FPGAEmulator()
                self.connection.open()
            else:
                self.connection = self._open_serial()
    
    def _open_serial(self):
        """
        Open a serial connection to the IACQ device.
        """
        
        try:
            serialConnection = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            return serialConnection
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            return None
        
    def close_connection(self):  
        self.connection.close()

    def send_command(self, command):
        """
        Send a command to the IACQ device or emulator.

        Args:
            command: Command string to send
        """
        if self.connection is None:
            print("Connection not open. Call open_connection() first.")
            return        
       
        self.connection.write(command.encode())

    def read_response(self):   
        """
        Read a response from the IACQ device or emulator.

        Returns:
            Response string from the device
        """
        if self.connection is None:
            print("Connection not open. Call open_connection() first.")
            return None
        
        response = self.connection.readline().decode().strip()
        return response   

    def __enter__(self):
        self.open_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection() 
        return False  # Don't suppress exceptions

with IACQ(port='COM8', emulator=False) as iacq:
    test_key = bytes.fromhex("8A55114D1CB6A9A2BE263D4D7AECAAFF")
    iacq.connection.write(bytes([0x4B]) + test_key)  # K command
    #iacq.send_command('K')
    response = iacq.read_response()
    print(f"Received response: {response}")

            
    
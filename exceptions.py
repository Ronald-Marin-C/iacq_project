# exceptions.py

class FPGAError(Exception):
    """Base exception for all FPGA-related errors.

    Example:
        >>> try:
        ...     # FPGA operations
        ...     pass
        ... except FPGAError as e:
        ...     print(f"FPGA operation failed: {e}")
    """
    pass

class FPGAConnectionError(FPGAError):
    """Exception raised when a connection cannot be established or was lost.

    Example:
        >>> if not connection.is_open:
        ...     raise FPGAConnectionError("Failed to connect to COM3")
    """
    pass

class FPGATimeoutError(FPGAError):
    """Exception raised when the FPGA did not respond within the timeout period.

    Example:
        >>> if not response:
        ...     raise FPGATimeoutError("Read operation timed out after 1.0s")
    """
    pass

class FPGAValidationError(FPGAError):
    """Exception raised when input data fails validation (e.g., wrong type or length).

    Example:
        >>> if len(key) != 16:
        ...     raise FPGAValidationError("Key must be exactly 16 bytes")
    """
    pass

class FPGAProtocolError(FPGAError):
    """Exception raised when the response from the FPGA was malformed or unexpected.

    Example:
        >>> if response != "OK":
        ...     raise FPGAProtocolError("Expected 'OK', got an invalid response")
    """
    pass

class FPGAAuthenticationError(FPGAError):
    """Exception raised when authentication fails during decryption.
    
    This usually indicates a tag mismatch, corrupted data during 
    transmission, or an incorrect key/nonce combination.

    Example:
        >>> if received_tag != expected_tag:
        ...     raise FPGAAuthenticationError("Tag mismatch: Data integrity not verified")
    """
    pass
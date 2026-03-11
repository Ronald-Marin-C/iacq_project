# exceptions.py

class FPGAError(Exception):
    """Base exception for all FPGA-related errors."""
    pass

class FPGAConnectionError(FPGAError):
    """Connection cannot be established or was lost."""
    pass

class FPGATimeoutError(FPGAError):
    """FPGA did not respond within timeout period."""
    pass

class FPGAValidationError(FPGAError):
    """Input data failed validation (e.g., wrong type or length)."""
    pass

class FPGAProtocolError(FPGAError):
    """Response from FPGA was malformed or unexpected."""
    pass
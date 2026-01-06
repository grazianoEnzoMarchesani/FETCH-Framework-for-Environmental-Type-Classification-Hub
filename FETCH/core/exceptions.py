# -*- coding: utf-8 -*-
"""
FETCH Custom Exceptions Module

Defines a hierarchy of custom exceptions for stratified error handling.
Distinguishes between critical errors (task abort) and warnings (non-blocking).
"""


class FetchError(Exception):
    """
    Base exception for all FETCH plugin errors.
    
    Attributes:
        message: Technical error message for logs
        user_message: User-friendly message for UI display
        recoverable: If True, the error is non-blocking and processing can continue
    """
    
    def __init__(self, message, user_message=None, recoverable=False):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or message
        self.recoverable = recoverable
    
    def __str__(self):
        return self.message


class FetchDataError(FetchError):
    """
    Error during data download or acquisition.
    
    Examples:
        - Network connection failure
        - API rate limiting
        - Invalid credentials
        - Data source unavailable
    """
    
    def __init__(self, message, user_message=None, source=None, recoverable=False):
        super().__init__(message, user_message, recoverable)
        self.source = source  # Name of the data source that failed


class FetchProcessError(FetchError):
    """
    Error during data processing or calculation.
    
    Examples:
        - Raster processing failure
        - Vector operation error
        - Invalid input data
        - Calculation algorithm failure
    """
    
    def __init__(self, message, user_message=None, process=None, recoverable=False):
        super().__init__(message, user_message, recoverable)
        self.process = process  # Name of the process that failed


class FetchConfigError(FetchError):
    """
    Configuration or setup error.
    
    Examples:
        - Missing configuration file
        - Invalid project setup
        - Missing required data
        - CRS mismatch
    """
    
    def __init__(self, message, user_message=None, config_key=None, recoverable=False):
        super().__init__(message, user_message, recoverable)
        self.config_key = config_key  # Configuration key that caused the error


class FetchWarning(FetchError):
    """
    Non-blocking warning - task can continue.
    
    Use this for issues that should be logged but don't prevent 
    the overall operation from completing.
    
    Examples:
        - Optional data source unavailable
        - Non-critical processing step skipped
        - Fallback method used
    """
    
    def __init__(self, message, user_message=None):
        super().__init__(message, user_message, recoverable=True)


class FetchCriticalError(FetchError):
    """
    Critical error - task must abort immediately.
    
    Use this for errors that make it impossible to continue
    with the current operation.
    
    Examples:
        - Required input data missing
        - Core processing failure
        - System resource exhausted
        - Unrecoverable state
    """
    
    def __init__(self, message, user_message=None):
        super().__init__(message, user_message, recoverable=False)


# Utility function for error handling in tasks
def handle_fetch_error(error, log_callback=None, task_log_func=None):
    """
    Handle a FetchError according to its type and severity.
    
    Args:
        error: FetchError instance
        log_callback: Optional callback for logging to UI
        task_log_func: Optional QGIS log function
        
    Returns:
        bool: True if processing should continue, False if it should abort
    """
    from qgis.core import Qgis
    
    level = Qgis.Warning if error.recoverable else Qgis.Critical
    prefix = "⚠" if error.recoverable else "✗"
    
    log_message = f"{prefix} {error.user_message}"
    
    if task_log_func:
        task_log_func(log_message, level)
    
    if log_callback:
        log_callback(log_message)
    
    return error.recoverable

# -*- coding: utf-8 -*-
"""
EnviProtocol Custom Exceptions Module

Defines a hierarchy of custom exceptions for stratified error handling.
Distinguishes between critical errors (task abort) and warnings (non-blocking).
"""


class EnviError(Exception):
    """
    Base exception for all EnviProtocol plugin errors.
    
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


class EnviDataError(EnviError):
    """
    Error during data download or acquisition.
    """
    
    def __init__(self, message, user_message=None, source=None, recoverable=False):
        super().__init__(message, user_message, recoverable)
        self.source = source  # Name of the data source that failed


class EnviCriticalError(EnviError):
    """
    Critical error - task must abort immediately.
    """
    
    def __init__(self, message, user_message=None):
        super().__init__(message, user_message, recoverable=False)

"""
converter/services/exceptions.py

Custom exception hierarchy for the converter app.
All converter-related errors ultimately derive from ConversionError so
callers only need to catch that one base class.
"""


class ConversionError(Exception):
    """Base class for all conversion errors."""


class UnsupportedFormatError(ConversionError):
    """Raised when the requested source→target pair has no registered converter."""


class FileMissingError(ConversionError):
    """Raised when the source file does not exist on disk."""


class CorruptedFileError(ConversionError):
    """Raised when the source file cannot be opened/parsed."""


class ConversionFailedError(ConversionError):
    """Raised when the conversion process itself fails."""

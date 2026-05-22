"""
converter/services/__init__.py

Public surface of the converter services package.

Importing from this module guarantees all converters are registered
because ``conversion_manager`` triggers all service-module imports.
"""

from .conversion_manager import ConversionManager  # noqa: F401 — re-export
from .exceptions import (  # noqa: F401
    ConversionError,
    ConversionFailedError,
    CorruptedFileError,
    FileMissingError,
    UnsupportedFormatError,
)
from .registry import registry  # noqa: F401

__all__ = [
    "ConversionManager",
    "registry",
    "ConversionError",
    "UnsupportedFormatError",
    "FileMissingError",
    "CorruptedFileError",
    "ConversionFailedError",
]

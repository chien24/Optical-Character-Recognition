"""
converter/services/registry.py

Central registry that maps (source_format, target_format) pairs to their
converter instances.  All registered converters are plain singletons —
one instance per supported pair — because they carry no per-request state.

Usage
-----
    from converter.services.registry import registry

    converter = registry.get("pdf", "txt")
    converter.convert(src_path, dst_path)

Extending
---------
To add a new format pair, call ``registry.register()`` with a converter
instance **after** defining it, or let each service module call it on
import.  ``conversion_manager.py`` imports every service module so all
registrations happen before any request is processed.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from .base import BaseConverter
from .exceptions import UnsupportedFormatError

logger = logging.getLogger(__name__)

# Internal type alias for a format pair key.
_FormatPair = Tuple[str, str]


class ConverterRegistry:
    """Thread-safe (read-only after startup) registry for converters."""

    def __init__(self) -> None:
        self._converters: Dict[_FormatPair, BaseConverter] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, converter: BaseConverter) -> None:
        """Register a converter instance.

        Args:
            converter: A concrete :class:`BaseConverter` instance.  The
                       ``source_format`` and ``target_format`` attributes
                       are used as the registry key.

        Raises:
            ValueError: If the pair is already registered (prevents silent
                        overwrites which could hide mis-configuration).
        """
        key: _FormatPair = (converter.source_format, converter.target_format)
        if key in self._converters:
            raise ValueError(
                f"A converter for {key} is already registered: "
                f"{self._converters[key].__class__.__name__}"
            )
        self._converters[key] = converter
        logger.debug("Registered converter %s for %s", converter.__class__.__name__, key)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, source_format: str, target_format: str) -> BaseConverter:
        """Return the converter for the given pair.

        Args:
            source_format: Lowercase extension of the source file, e.g. ``"pdf"``.
            target_format: Lowercase extension of the desired output, e.g. ``"txt"``.

        Raises:
            UnsupportedFormatError: When no converter is registered for the pair.
        """
        key: _FormatPair = (source_format.lower(), target_format.lower())
        converter = self._converters.get(key)
        if converter is None:
            supported = self.supported_pairs()
            raise UnsupportedFormatError(
                f"No converter registered for {source_format!r} → {target_format!r}. "
                f"Supported pairs: {supported}"
            )
        return converter

    def is_supported(self, source_format: str, target_format: str) -> bool:
        """Return ``True`` if the pair is registered."""
        return (source_format.lower(), target_format.lower()) in self._converters

    def supported_pairs(self) -> list[_FormatPair]:
        """Return a sorted list of all registered (source, target) pairs."""
        return sorted(self._converters.keys())

    def supported_targets_for(self, source_format: str) -> list[str]:
        """Return all target formats available for a given source format."""
        src = source_format.lower()
        return sorted(t for (s, t) in self._converters if s == src)

    def supported_sources(self) -> list[str]:
        """Return distinct source formats across all registrations."""
        return sorted({s for (s, _) in self._converters})


# Module-level singleton — import this everywhere.
registry = ConverterRegistry()

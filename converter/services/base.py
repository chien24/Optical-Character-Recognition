"""
converter/services/base.py

Abstract base class for all format-specific converters.

Each concrete converter MUST implement `convert()` and declare the
class-level `source_format` / `target_format` pair so the registry can
discover it automatically.
"""

from __future__ import annotations

import abc
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseConverter(abc.ABC):
    """Interface every format converter must satisfy."""

    #: Override in subclasses, e.g. "pdf"
    source_format: str = ""
    #: Override in subclasses, e.g. "txt"
    target_format: str = ""

    @abc.abstractmethod
    def convert(self, input_path: Path, output_path: Path) -> Path:
        """Perform the conversion and return the path to the output file.

        Args:
            input_path:  Absolute path to the source file.
            output_path: Absolute path where the result should be written.

        Returns:
            The resolved output path (may differ if the tool renames the file).

        Raises:
            ConversionError: on any failure during conversion.
        """

    # ------------------------------------------------------------------
    # Convenience helpers available to subclasses
    # ------------------------------------------------------------------

    def _ensure_parent(self, path: Path) -> None:
        """Create parent directories if they do not exist."""
        path.parent.mkdir(parents=True, exist_ok=True)

    def _log_start(self, src: Path, dst: Path) -> None:
        logger.info(
            "[%s→%s] Starting conversion: %s → %s",
            self.source_format,
            self.target_format,
            src.name,
            dst.name,
        )

    def _log_done(self, dst: Path) -> None:
        logger.info(
            "[%s→%s] Conversion complete: %s",
            self.source_format,
            self.target_format,
            dst.name,
        )

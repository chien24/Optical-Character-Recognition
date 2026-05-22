"""
converter/services/image_service.py

Converter for Image → PDF using Pillow.

Supported source formats: png, jpg, jpeg, bmp, webp, tiff
Output: single-page PDF preserving original image quality.

Registered pairs
----------------
- png  → pdf  (ImageToPdfConverter)
- jpg  → pdf
- jpeg → pdf
- bmp  → pdf
- webp → pdf
- tiff → pdf
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import BaseConverter
from .exceptions import ConversionFailedError, CorruptedFileError, FileMissingError
from .registry import registry

logger = logging.getLogger(__name__)

try:
    from PIL import Image as _PillowImage
    _PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PillowImage = None  # type: ignore
    _PILLOW_AVAILABLE = False
    logger.warning(
        "Pillow is not installed; Image→PDF conversions will be unavailable. "
        "Install it with: pip install Pillow"
    )

# Source formats this service handles.
_IMAGE_FORMATS = ("png", "jpg", "jpeg", "bmp", "webp", "tiff")


class ImageToPdfConverter(BaseConverter):
    """Convert a raster image to a single-page PDF using Pillow.

    The image is embedded at its native resolution; no re-scaling is applied
    so quality is fully preserved.
    """

    # These are set dynamically per-instance so the same class can be
    # registered multiple times for different source extensions.
    def __init__(self, source_fmt: str) -> None:
        self.source_format: str = source_fmt
        self.target_format: str = "pdf"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        """Open the image and save it as a PDF.

        Args:
            input_path:  Path to the source image.
            output_path: Desired path for the output .pdf.

        Returns:
            Resolved ``output_path``.

        Raises:
            FileMissingError:      Source image not found.
            CorruptedFileError:    Pillow cannot open the image.
            ConversionFailedError: Any other processing failure.
        """
        if not input_path.exists():
            raise FileMissingError(f"Source image not found: {input_path}")
        self._log_start(input_path, output_path)
        self._ensure_parent(output_path)

        if not _PILLOW_AVAILABLE:
            raise ConversionFailedError(
                "Pillow is not installed. Install it with: pip install Pillow"
            )
        try:
            img = _PillowImage.open(str(input_path))
        except Exception as exc:
            raise CorruptedFileError(
                f"Cannot open image '{input_path.name}': {exc}"
            ) from exc

        try:
            # Pillow requires RGB mode to save as PDF.
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            elif img.mode == "RGBA":
                # PDF does not support transparency natively in Pillow's writer;
                # composite onto white background.
                background = _PillowImage.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            img.save(str(output_path), "PDF", resolution=100.0)
        except Exception as exc:
            raise ConversionFailedError(
                f"Failed to convert image '{input_path.name}' to PDF: {exc}"
            ) from exc
        finally:
            img.close()

        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Register one converter instance per source format
# ---------------------------------------------------------------------------

for _fmt in _IMAGE_FORMATS:
    registry.register(ImageToPdfConverter(source_fmt=_fmt))

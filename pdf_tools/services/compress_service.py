"""Compress PDF service — reduce file size via garbage collection and optional image downsampling."""

from __future__ import annotations

import logging
import os
from typing import Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import CompressError
from .utils import open_pdf, get_output_path

logger = logging.getLogger(__name__)


def compress_pdf(
    file_path: str,
    output_path: Optional[str] = None,
    image_quality: int = 80,
    linearize: bool = False,
) -> str:
    """Compress a PDF by running garbage collection and deflating streams.

    Optionally downsample embedded JPEG images to reduce file size further.

    Args:
        file_path: Absolute path to source PDF.
        output_path: Destination path. Auto-generated if None.
        image_quality: Target JPEG quality (1-100) for image recompression.
                       Set to 100 to skip image recompression.
        linearize: If True, produce a web-optimised (linearized) PDF.

    Returns:
        Absolute path to the compressed output PDF.

    Raises:
        CompressError: if compression fails.
    """
    if not (1 <= image_quality <= 100):
        raise CompressError("image_quality must be between 1 and 100.")

    if output_path is None:
        output_path = get_output_path("compressed")

    logger.info(
        "Compressing %s (quality=%d, linearize=%s)", file_path, image_quality, linearize
    )

    src = open_pdf(file_path)

    try:
        # Optionally recompress JPEG images
        if image_quality < 100:
            _recompress_images(src, image_quality)

        original_size = os.path.getsize(file_path)

        # Save with maximum garbage collection (garbage=4) and deflation
        src.save(
            output_path,
            garbage=4,         # Remove all unreferenced objects
            deflate=True,      # Compress streams
            deflate_images=True,
            deflate_fonts=True,
            linear=linearize,
            clean=True,        # Clean up syntax errors
        )

        compressed_size = os.path.getsize(output_path)
        reduction_pct = (1 - compressed_size / original_size) * 100 if original_size else 0

        logger.info(
            "Compression complete: %d → %d bytes (%.1f%% reduction) → %s",
            original_size,
            compressed_size,
            reduction_pct,
            output_path,
        )

    except CompressError:
        raise
    except Exception as exc:
        raise CompressError(f"Compression failed: {exc}") from exc
    finally:
        src.close()

    return output_path


def _recompress_images(doc: fitz.Document, quality: int) -> None:
    """Recompress all JPEG images in a document to reduce their size in place.

    This modifies the document object before saving.

    Args:
        doc: Open fitz.Document (modified in place).
        quality: JPEG quality 1-100.
    """
    try:
        from PIL import Image
        import io
        PIL_AVAILABLE = True
    except ImportError:
        logger.warning("Pillow not available; skipping image recompression.")
        PIL_AVAILABLE = False

    if not PIL_AVAILABLE:
        return

    for xref in range(1, doc.xref_length()):
        try:
            if doc.xref_get_key(xref, "Subtype") != ("name", "Image"):
                continue

            base_image = doc.extract_image(xref)
            img_bytes = base_image.get("image", b"")
            img_ext = base_image.get("ext", "").lower()

            # Only recompress JPEG images
            if img_ext not in ("jpeg", "jpg"):
                continue

            img = Image.open(io.BytesIO(img_bytes))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            new_bytes = buf.getvalue()

            if len(new_bytes) < len(img_bytes):
                doc.update_stream(xref, new_bytes)
                logger.debug(
                    "Recompressed image xref=%d: %d → %d bytes",
                    xref, len(img_bytes), len(new_bytes),
                )

        except Exception as exc:
            logger.debug("Skipping image xref=%d during recompression: %s", xref, exc)

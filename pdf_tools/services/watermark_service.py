"""Watermark service — add text or image watermarks to PDF pages."""

from __future__ import annotations

import logging
import math
import os
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from pdf_tools.exceptions import WatermarkError
from .utils import open_pdf, save_pdf, get_output_path, compute_watermark_rect

logger = logging.getLogger(__name__)

VALID_POSITIONS = ("center", "top-left", "top-right", "bottom-left", "bottom-right")


def add_text_watermark(
    file_path: str,
    text: str,
    output_path: Optional[str] = None,
    opacity: float = 0.3,
    position: str = "center",
    font_size: int = 48,
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
    rotate: float = 45.0,
    pages: Optional[List[int]] = None,
) -> str:
    """Add a text watermark to PDF pages.

    Args:
        file_path: Source PDF path.
        text: Watermark text string.
        output_path: Destination path. Auto-generated if None.
        opacity: 0.0 (transparent) to 1.0 (opaque).
        position: One of VALID_POSITIONS.
        font_size: Font size in points.
        color: RGB tuple (each 0.0-1.0).
        rotate: Text rotation angle in degrees (default 45°).
        pages: 1-indexed page list. None = all pages.

    Returns:
        Absolute path to the watermarked output PDF.

    Raises:
        WatermarkError: if watermarking fails.
    """
    if not text.strip():
        raise WatermarkError("Watermark text must not be empty.")
    if position not in VALID_POSITIONS:
        raise WatermarkError(f"position must be one of {VALID_POSITIONS}.")
    if not (0.0 <= opacity <= 1.0):
        raise WatermarkError("opacity must be between 0.0 and 1.0.")

    if output_path is None:
        output_path = get_output_path("watermarked_text")

    src = open_pdf(file_path)
    page_count = src.page_count

    # Determine target pages (0-indexed)
    if pages:
        pages_0 = [p - 1 for p in pages if 1 <= p <= page_count]
    else:
        pages_0 = list(range(page_count))

    logger.info("Adding text watermark '%s' to %d pages of %s", text, len(pages_0), file_path)

    try:
        for i in pages_0:
            page = src[i]
            _insert_text_watermark(page, text, opacity, position, font_size, color, rotate)

        save_pdf(src, output_path)
    except WatermarkError:
        raise
    except Exception as exc:
        src.close()
        raise WatermarkError(f"Text watermark failed: {exc}") from exc

    logger.info("Text watermark complete → %s", output_path)
    return output_path


def _insert_text_watermark(
    page: fitz.Page,
    text: str,
    opacity: float,
    position: str,
    font_size: int,
    color: Tuple[float, float, float],
    rotate: float,
) -> None:
    """Insert a text watermark on a single page using an overlay annotation."""
    rect = page.rect

    # Estimate text bounding box
    text_width = font_size * len(text) * 0.6  # rough estimate
    text_height = font_size * 1.2

    wm_rect = compute_watermark_rect(rect, text_width, text_height, position)

    # Insert text at computed position
    page.insert_text(
        point=fitz.Point(wm_rect.x0, wm_rect.y1),
        text=text,
        fontsize=font_size,
        color=color,
        rotate=rotate,
        fill_opacity=opacity,
        stroke_opacity=opacity,
    )


def add_image_watermark(
    file_path: str,
    watermark_image_path: str,
    output_path: Optional[str] = None,
    opacity: float = 0.3,
    position: str = "center",
    pages: Optional[List[int]] = None,
) -> str:
    """Add an image watermark to PDF pages.

    Args:
        file_path: Source PDF path.
        watermark_image_path: Absolute path to the watermark image (PNG/JPEG/etc.).
        output_path: Destination path. Auto-generated if None.
        opacity: 0.0 (transparent) to 1.0 (opaque). Applied via PDF opacity mask.
        position: One of VALID_POSITIONS.
        pages: 1-indexed page list. None = all pages.

    Returns:
        Absolute path to the watermarked output PDF.

    Raises:
        WatermarkError: if watermarking fails.
    """
    if not os.path.isfile(watermark_image_path):
        raise WatermarkError(f"Watermark image not found: {watermark_image_path!r}")
    if position not in VALID_POSITIONS:
        raise WatermarkError(f"position must be one of {VALID_POSITIONS}.")
    if not (0.0 <= opacity <= 1.0):
        raise WatermarkError("opacity must be between 0.0 and 1.0.")

    if output_path is None:
        output_path = get_output_path("watermarked_image")

    src = open_pdf(file_path)
    page_count = src.page_count

    if pages:
        pages_0 = [p - 1 for p in pages if 1 <= p <= page_count]
    else:
        pages_0 = list(range(page_count))

    # Load watermark image dimensions
    try:
        wm_img = fitz.open(watermark_image_path)
        # Get image dimensions from the first page of the image doc (for SVG/PDF)
        # or use the raw image dimensions
        wm_pix = fitz.Pixmap(wm_img, 0) if wm_img.page_count > 0 else None
    except Exception:
        # Fallback: treat as raster image
        wm_img = None
        wm_pix = fitz.Pixmap(watermark_image_path)

    logger.info(
        "Adding image watermark from %s to %d pages of %s",
        watermark_image_path, len(pages_0), file_path
    )

    try:
        for i in pages_0:
            page = src[i]
            page_rect = page.rect

            # Default watermark to 40% of page width, maintaining aspect ratio
            if wm_pix:
                wm_w_orig, wm_h_orig = wm_pix.width, wm_pix.height
            else:
                wm_w_orig = wm_h_orig = 200  # fallback

            target_width = page_rect.width * 0.4
            scale = target_width / wm_w_orig if wm_w_orig > 0 else 1.0
            target_height = wm_h_orig * scale

            wm_rect = compute_watermark_rect(
                page_rect, target_width, target_height, position
            )

            # Insert image with opacity
            page.insert_image(
                wm_rect,
                filename=watermark_image_path,
                overlay=True,
                xref=0,  # let fitz auto-assign
            )

            # Apply opacity via PDF transparency group (best-effort)
            # Full opacity control requires PDF form XObject; fitz insert_image
            # does not expose per-image opacity natively. As workaround we add
            # a rectangle overlay with complementary fill to simulate transparency.
            if opacity < 1.0:
                alpha_fill = 1.0 - opacity
                page.draw_rect(
                    wm_rect,
                    color=None,
                    fill=(1, 1, 1),  # white fill
                    fill_opacity=alpha_fill,
                    overlay=True,
                )

        save_pdf(src, output_path)
    except WatermarkError:
        raise
    except Exception as exc:
        src.close()
        raise WatermarkError(f"Image watermark failed: {exc}") from exc
    finally:
        if wm_pix:
            wm_pix = None

    logger.info("Image watermark complete → %s", output_path)
    return output_path

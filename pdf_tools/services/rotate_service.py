"""Rotate pages service — rotate selected (or all) pages by 90/180/270 degrees."""

from __future__ import annotations

import logging
from typing import List, Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import RotateError
from .utils import open_pdf, save_pdf, get_output_path

logger = logging.getLogger(__name__)

VALID_ANGLES = (90, 180, 270)


def rotate_pages(
    file_path: str,
    pages: List[int],
    angle: int,
    output_path: Optional[str] = None,
) -> str:
    """Rotate selected pages (or all pages if pages is empty) in a PDF.

    Args:
        file_path: Absolute path to source PDF.
        pages: 1-indexed list of pages to rotate. Empty list = rotate all pages.
        angle: Rotation angle in degrees: 90, 180, or 270.
        output_path: Destination path. Auto-generated if None.

    Returns:
        Absolute path to the rotated output PDF.

    Raises:
        RotateError: if rotation fails or angle is invalid.
    """
    if angle not in VALID_ANGLES:
        raise RotateError(
            f"Invalid angle {angle}. Must be one of {VALID_ANGLES}."
        )

    if output_path is None:
        output_path = get_output_path(f"rotated_{angle}deg")

    src = open_pdf(file_path)
    page_count = src.page_count

    # Determine target pages (0-indexed)
    if pages:
        invalid = [p for p in pages if p < 1 or p > page_count]
        if invalid:
            src.close()
            raise RotateError(
                f"Invalid page numbers {invalid!r} for a {page_count}-page document."
            )
        pages_0 = [p - 1 for p in pages]
    else:
        pages_0 = list(range(page_count))

    logger.info(
        "Rotating %d page(s) by %d° in %s", len(pages_0), angle, file_path
    )

    try:
        for i in pages_0:
            page = src[i]
            # fitz page.set_rotation accepts cumulative rotation
            current_rotation = page.rotation
            new_rotation = (current_rotation + angle) % 360
            page.set_rotation(new_rotation)
            logger.debug("Page %d: %d° → %d°", i + 1, current_rotation, new_rotation)

        save_pdf(src, output_path)
    except RotateError:
        raise
    except Exception as exc:
        src.close()
        raise RotateError(f"Rotate pages failed: {exc}") from exc

    logger.info("Rotation complete → %s", output_path)
    return output_path

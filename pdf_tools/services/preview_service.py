"""Preview service — render PDF pages to thumbnail images."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import PreviewError
from .utils import open_pdf, ensure_output_dir, get_output_path

logger = logging.getLogger(__name__)

DEFAULT_DPI = 150
THUMBNAIL_DPI = 100


def generate_preview(
    file_path: str,
    page_num: int = 1,
    output_path: Optional[str] = None,
    dpi: int = DEFAULT_DPI,
    fmt: str = "PNG",
) -> str:
    """Render a single PDF page to an image file.

    Args:
        file_path: Absolute path to source PDF.
        page_num: 1-indexed page number to render.
        output_path: Destination image path. Auto-generated if None.
        dpi: Resolution in dots-per-inch (36-600). Default 150.
        fmt: Output image format ("PNG" or "JPEG"). Default "PNG".

    Returns:
        Absolute path to the generated image file.

    Raises:
        PreviewError: if rendering fails.
    """
    fmt = fmt.upper()
    ext = ".jpg" if fmt == "JPEG" else ".png"

    if output_path is None:
        output_path = get_output_path(f"preview_p{page_num}", suffix=ext, subdir="previews")

    src = open_pdf(file_path)
    page_count = src.page_count

    if not (1 <= page_num <= page_count):
        src.close()
        raise PreviewError(
            f"page_num {page_num} out of range [1, {page_count}]."
        )

    logger.info("Generating preview for page %d of %s (dpi=%d)", page_num, file_path, dpi)

    try:
        page = src[page_num - 1]
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 points = 1 inch
        pix = page.get_pixmap(matrix=mat, alpha=False)

        if fmt == "JPEG":
            pix.save(output_path, output="jpeg")
        else:
            pix.save(output_path)

        logger.info("Preview saved → %s (%dx%d px)", output_path, pix.width, pix.height)

    except PreviewError:
        raise
    except Exception as exc:
        raise PreviewError(f"Preview generation failed: {exc}") from exc
    finally:
        src.close()

    return output_path


def generate_all_previews(
    file_path: str,
    output_dir: Optional[str] = None,
    dpi: int = THUMBNAIL_DPI,
    fmt: str = "PNG",
) -> List[str]:
    """Render all pages of a PDF to image thumbnails.

    Args:
        file_path: Absolute path to source PDF.
        output_dir: Directory for output images. Auto-created if None.
        dpi: Resolution for thumbnails (lower = faster, smaller files).
        fmt: Output image format ("PNG" or "JPEG").

    Returns:
        Ordered list of absolute paths to generated image files.

    Raises:
        PreviewError: if rendering fails on any page.
    """
    fmt = fmt.upper()
    ext = ".jpg" if fmt == "JPEG" else ".png"

    if output_dir is None:
        output_dir = ensure_output_dir("previews")
    os.makedirs(output_dir, exist_ok=True)

    src = open_pdf(file_path)
    page_count = src.page_count
    output_paths: List[str] = []

    logger.info(
        "Generating %d page previews for %s (dpi=%d)", page_count, file_path, dpi
    )

    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)

        for i in range(page_count):
            page = src[i]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_path = os.path.join(output_dir, f"page_{i + 1:04d}{ext}")

            if fmt == "JPEG":
                pix.save(img_path, output="jpeg")
            else:
                pix.save(img_path)

            output_paths.append(img_path)
            logger.debug("Rendered page %d → %s", i + 1, img_path)

    except PreviewError:
        raise
    except Exception as exc:
        raise PreviewError(f"generate_all_previews failed: {exc}") from exc
    finally:
        src.close()

    logger.info("All previews generated: %d images", len(output_paths))
    return output_paths

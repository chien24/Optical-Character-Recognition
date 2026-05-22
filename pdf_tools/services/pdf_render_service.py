"""pdf_tools/services/pdf_render_service.py

Per-page PDF rendering and text detection for the OCR pipeline.

This service is the ONLY component in the system that understands PDF internals.
All outputs are plain Python objects — PIL.Image or str.
The OCR engine never receives fitz objects or raw PDF paths.

Boundary contract:
    Input  → PDF file path (str)
    Output → PIL.Image (scanned pages) or str (text-based pages)

Per-page hybrid support:
    Each page is classified independently:
        - page has text layer (>= text_threshold chars) → direct text extraction
        - page is scanned / image-only               → render to PIL.Image for OCR
    This means a single PDF can mix text pages and scanned pages correctly.
"""
from __future__ import annotations

import io
import logging
from typing import Generator, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image

from pdf_tools.exceptions import ExtractError, InvalidPDFError
from .utils import open_pdf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum characters extracted via get_text() to treat a page as "text-based".
# Pages below this threshold are assumed to be scanned images and will be OCR'd.
_DEFAULT_TEXT_THRESHOLD = 20


# ---------------------------------------------------------------------------
# Page-level helpers
# ---------------------------------------------------------------------------

def _page_has_text(page: fitz.Page, min_chars: int = _DEFAULT_TEXT_THRESHOLD) -> bool:
    """Return True if *page* has enough extractable text to skip OCR.

    Args:
        page:      An open fitz.Page object.
        min_chars: Minimum character count (after strip) to classify as text-based.

    Returns:
        True  → page has a text layer; use direct extraction.
        False → page appears to be a scanned image; render and OCR.
    """
    try:
        text = page.get_text("text").strip()
        return len(text) >= min_chars
    except Exception:
        return False


def extract_page_text(page: fitz.Page) -> str:
    """Return plain text from a single fitz.Page.

    Args:
        page: An open fitz.Page object.

    Returns:
        Stripped plain text string.

    Raises:
        ExtractError: if fitz fails to extract text.
    """
    try:
        return page.get_text("text").strip()
    except Exception as exc:
        raise ExtractError(f"Failed to extract text from PDF page: {exc}") from exc


def render_page_to_pil(page: fitz.Page, dpi: int = 300) -> Image.Image:
    """Render a single fitz.Page to a PIL.Image at the given DPI.

    Args:
        page: An open fitz.Page object.
        dpi:  Render resolution. 300 DPI is recommended for OCR quality;
              lower values (150) are faster for previews.

    Returns:
        PIL.Image in RGB mode.

    Raises:
        ExtractError: if rendering or format conversion fails.
    """
    try:
        zoom = dpi / 72.0  # fitz uses 72 DPI as its base unit
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return pil_img
    except Exception as exc:
        raise ExtractError(f"Failed to render PDF page to image: {exc}") from exc


# ---------------------------------------------------------------------------
# Generator API — avoids loading all pages into memory simultaneously
# ---------------------------------------------------------------------------

def iter_pdf_pages(
    pdf_path: str,
    *,
    dpi: int = 300,
    text_threshold: int = _DEFAULT_TEXT_THRESHOLD,
) -> Generator[Tuple[int, str, Optional[Image.Image], str], None, None]:
    """Iterate over PDF pages one at a time with per-page hybrid classification.

    Each page is independently assessed:
        - text-based pages  → yield (page_num, "direct_text", None, text_str)
        - scanned/img pages → yield (page_num, "ocr", PIL.Image, "")

    Using a generator means only one page image is in memory at a time,
    which is safe for large multi-page PDFs.

    Args:
        pdf_path:       Absolute path to the PDF file.
        dpi:            Render resolution for scanned pages (default 300).
        text_threshold: Minimum characters to classify a page as text-based.

    Yields:
        Tuple of (page_num, method, pil_image, direct_text):
            page_num    (int)           : 1-indexed page number
            method      (str)           : "direct_text" | "ocr"
            pil_image   (Image|None)    : PIL.Image when method=="ocr", else None
            direct_text (str)           : extracted text when method=="direct_text", else ""

    Raises:
        InvalidPDFError: if the PDF cannot be opened (propagated from open_pdf).
        ExtractError:   if a page fails to render or its text cannot be read.
    """
    doc = open_pdf(pdf_path)
    page_count = doc.page_count
    logger.info(
        "PDF opened: %s (%d page%s)",
        pdf_path, page_count, "s" if page_count != 1 else "",
    )

    try:
        for i in range(page_count):
            page = doc[i]
            page_num = i + 1

            if _page_has_text(page, min_chars=text_threshold):
                text = extract_page_text(page)
                logger.debug(
                    "Page %d/%d → direct_text (%d chars)",
                    page_num, page_count, len(text),
                )
                yield (page_num, "direct_text", None, text)

            else:
                logger.debug(
                    "Page %d/%d → OCR render @ %d DPI",
                    page_num, page_count, dpi,
                )
                pil_img = render_page_to_pil(page, dpi=dpi)
                yield (page_num, "ocr", pil_img, "")

    finally:
        doc.close()
        logger.debug("PDF closed: %s", pdf_path)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def get_pdf_page_count(pdf_path: str) -> int:
    """Return the total page count for a PDF without iterating all pages.

    Args:
        pdf_path: Absolute path to the PDF file.

    Returns:
        Integer page count.

    Raises:
        InvalidPDFError: if the file cannot be opened.
    """
    doc = open_pdf(pdf_path)
    count = doc.page_count
    doc.close()
    return count

"""
Shared utilities for pdf_tools services.

All service modules should import helpers from here to ensure consistent
file handling, path generation, and PDF validation.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import List, Tuple

import fitz  # PyMuPDF

from django.conf import settings

from pdf_tools.exceptions import InvalidPDFError, PageRangeError, EncryptedPDFError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

PDF_OUTPUT_DIR = os.path.join(settings.MEDIA_ROOT, "pdf_tools")


def ensure_output_dir(subdir: str = "") -> str:
    """Create and return an output directory path under MEDIA_ROOT/pdf_tools/."""
    path = os.path.join(PDF_OUTPUT_DIR, subdir) if subdir else PDF_OUTPUT_DIR
    os.makedirs(path, exist_ok=True)
    return path


def get_output_path(prefix: str, suffix: str = ".pdf", subdir: str = "") -> str:
    """Generate a unique output file path under the pdf_tools media directory."""
    out_dir = ensure_output_dir(subdir)
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}{suffix}"
    return os.path.join(out_dir, filename)


# ---------------------------------------------------------------------------
# PDF open / save helpers
# ---------------------------------------------------------------------------

def open_pdf(path: str, password: str = "") -> fitz.Document:
    """Open a PDF file and return a fitz.Document.

    Raises:
        InvalidPDFError: if the file cannot be opened as a PDF.
        EncryptedPDFError: if the file is password-protected and no/wrong password provided.
    """
    if not os.path.isfile(path):
        raise InvalidPDFError(f"File not found: {path!r}")

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise InvalidPDFError(f"Cannot open PDF file {path!r}: {exc}") from exc

    if doc.is_encrypted:
        if not password:
            raise EncryptedPDFError(
                f"PDF {path!r} is encrypted. Provide a password."
            )
        authenticated = doc.authenticate(password)
        if not authenticated:
            raise EncryptedPDFError(f"Wrong password for encrypted PDF {path!r}.")

    if not doc.is_pdf:
        doc.close()
        raise InvalidPDFError(f"File {path!r} is not a PDF document.")

    return doc


def save_pdf(doc: fitz.Document, output_path: str, garbage: int = 4, deflate: bool = True) -> str:
    """Save a fitz Document to output_path with garbage collection.

    Args:
        doc: Open fitz.Document to save.
        output_path: Destination file path.
        garbage: Garbage collection level (0-4). 4 = most aggressive.
        deflate: Whether to deflate (compress) streams.

    Returns:
        output_path on success.
    """
    try:
        doc.save(output_path, garbage=garbage, deflate=deflate)
        logger.debug("Saved PDF to %s", output_path)
        return output_path
    except Exception as exc:
        raise RuntimeError(f"Failed to save PDF to {output_path!r}: {exc}") from exc
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Page range parsing
# ---------------------------------------------------------------------------

def parse_page_ranges(ranges_str: str, page_count: int) -> List[Tuple[int, int]]:
    """Parse a page range string like "1-3,5,7-9" into a list of (start, end) tuples.

    Pages are 1-indexed and inclusive on both ends.

    Args:
        ranges_str: e.g. "1-3,5,7-9"
        page_count: Total number of pages in the document.

    Returns:
        List of (start, end) tuples (1-indexed, inclusive).

    Raises:
        PageRangeError: if any range is invalid.
    """
    ranges_str = ranges_str.strip()
    if not ranges_str:
        raise PageRangeError("Page ranges string is empty.")

    result: List[Tuple[int, int]] = []
    tokens = re.split(r"[,\s]+", ranges_str)

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        if "-" in token:
            parts = token.split("-", 1)
            try:
                start, end = int(parts[0]), int(parts[1])
            except ValueError:
                raise PageRangeError(f"Invalid range token: {token!r}")
        else:
            try:
                start = end = int(token)
            except ValueError:
                raise PageRangeError(f"Invalid page number: {token!r}")

        if start < 1 or end > page_count or start > end:
            raise PageRangeError(
                f"Range ({start}-{end}) is invalid for a {page_count}-page document."
            )

        result.append((start, end))

    if not result:
        raise PageRangeError("No valid page ranges parsed.")

    return result


# ---------------------------------------------------------------------------
# Position helpers (for watermark placement)
# ---------------------------------------------------------------------------

def compute_watermark_rect(
    page_rect: fitz.Rect,
    wm_width: float,
    wm_height: float,
    position: str,
    margin: float = 20.0,
) -> fitz.Rect:
    """Compute the rectangle for placing a watermark on a page.

    Args:
        page_rect: The fitz.Rect of the page.
        wm_width: Watermark element width in points.
        wm_height: Watermark element height in points.
        position: One of 'center', 'top-left', 'top-right', 'bottom-left', 'bottom-right'.
        margin: Margin from edges for non-center positions.

    Returns:
        fitz.Rect for watermark placement.
    """
    pw, ph = page_rect.width, page_rect.height

    if position == "center":
        x0 = (pw - wm_width) / 2
        y0 = (ph - wm_height) / 2
    elif position == "top-left":
        x0, y0 = margin, margin
    elif position == "top-right":
        x0 = pw - wm_width - margin
        y0 = margin
    elif position == "bottom-left":
        x0 = margin
        y0 = ph - wm_height - margin
    elif position == "bottom-right":
        x0 = pw - wm_width - margin
        y0 = ph - wm_height - margin
    else:
        # Fallback to center
        x0 = (pw - wm_width) / 2
        y0 = (ph - wm_height) / 2

    return fitz.Rect(x0, y0, x0 + wm_width, y0 + wm_height)

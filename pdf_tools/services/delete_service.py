"""Delete pages service — remove selected pages from a PDF."""

from __future__ import annotations

import logging
from typing import List, Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import DeletePageError
from .utils import open_pdf, save_pdf, get_output_path

logger = logging.getLogger(__name__)


def delete_pages(
    file_path: str,
    pages: List[int],
    output_path: Optional[str] = None,
) -> str:
    """Create a new PDF with specified pages removed.

    Args:
        file_path: Absolute path to source PDF.
        pages: 1-indexed list of page numbers to delete.
               e.g. [2, 4] removes the 2nd and 4th pages.
        output_path: Destination path. Auto-generated if None.

    Returns:
        Absolute path to the output PDF.

    Raises:
        DeletePageError: if deletion fails or validation fails.
        ValueError: if all pages would be deleted.
    """
    if output_path is None:
        output_path = get_output_path("deleted_pages")

    src = open_pdf(file_path)
    page_count = src.page_count

    # Validate page numbers
    invalid = [p for p in pages if p < 1 or p > page_count]
    if invalid:
        src.close()
        raise DeletePageError(
            f"Invalid page numbers {invalid!r} for a {page_count}-page document."
        )

    if len(set(pages)) >= page_count:
        src.close()
        raise DeletePageError(
            "Cannot delete all pages from a PDF. At least one page must remain."
        )

    logger.info("Deleting pages %r from %s", pages, file_path)

    try:
        # fitz delete_page / select works by keeping pages NOT in the delete list
        # Convert to 0-indexed and deduplicate
        pages_to_delete_0 = sorted(set(p - 1 for p in pages), reverse=True)

        # Use fitz's built-in page deletion (modifies doc in place)
        for p0 in pages_to_delete_0:
            src.delete_page(p0)
            logger.debug("Deleted page at original index %d", p0 + 1)

        save_pdf(src, output_path)
    except DeletePageError:
        raise
    except Exception as exc:
        src.close()
        raise DeletePageError(f"Delete pages failed: {exc}") from exc

    logger.info("Delete pages complete → %s (%d pages remaining)", output_path, src.page_count)
    return output_path

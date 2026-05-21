"""Reorder pages service — create a new PDF with pages in a custom order."""

from __future__ import annotations

import logging
from typing import List, Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import ReorderError
from .utils import open_pdf, save_pdf, get_output_path

logger = logging.getLogger(__name__)


def reorder_pages(
    file_path: str,
    order: List[int],
    output_path: Optional[str] = None,
) -> str:
    """Create a new PDF with pages reordered according to the given order array.

    Args:
        file_path: Absolute path to source PDF.
        order: 0-indexed permutation of page indices.
               e.g. [2, 0, 1] for a 3-page doc means: page3, page1, page2.
        output_path: Destination path. Auto-generated if None.

    Returns:
        Absolute path to the reordered output PDF.

    Raises:
        ReorderError: if the operation fails.
        ValueError: if order is not a valid permutation.
    """
    if output_path is None:
        output_path = get_output_path("reordered")

    src = open_pdf(file_path)
    page_count = src.page_count

    # Validate order is a permutation of [0, page_count)
    if sorted(order) != list(range(page_count)):
        src.close()
        raise ReorderError(
            f"order must be a permutation of [0, {page_count}). Got: {order!r}"
        )

    logger.info("Reordering %d pages of %s", page_count, file_path)

    try:
        out_doc = fitz.open()
        for new_pos, old_idx in enumerate(order):
            out_doc.insert_pdf(src, from_page=old_idx, to_page=old_idx)
            logger.debug("Position %d ← original page %d", new_pos + 1, old_idx + 1)

        save_pdf(out_doc, output_path)
    except ReorderError:
        raise
    except Exception as exc:
        raise ReorderError(f"Reorder failed: {exc}") from exc
    finally:
        src.close()

    logger.info("Reorder complete → %s", output_path)
    return output_path

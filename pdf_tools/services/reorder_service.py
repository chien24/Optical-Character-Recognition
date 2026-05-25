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

    # Validate all elements in order are unique and within range [0, page_count)
    if not all(0 <= idx < page_count for idx in order):
        src.close()
        raise ReorderError(
            f"All indices in order must be between 0 and {page_count - 1}. Got: {order!r}"
        )
    if len(set(order)) != len(order):
        src.close()
        raise ReorderError(
            f"Indices in order must be unique. Got: {order!r}"
        )

    # If partial list is provided, append the rest of the page indices in order
    if len(order) < page_count:
        existing_set = set(order)
        remaining = [i for i in range(page_count) if i not in existing_set]
        full_order = list(order) + remaining
    else:
        full_order = list(order)

    logger.info("Reordering %d pages of %s", page_count, file_path)

    try:
        out_doc = fitz.open()
        for new_pos, old_idx in enumerate(full_order):
            out_doc.insert_pdf(src, from_page=old_idx, to_page=old_idx)
            logger.debug("Position %d ← original page %d", new_pos + 1, old_idx + 1)

        save_pdf(out_doc, output_path)
    except ReorderError:
        raise
    except Exception as exc:
        raise ReorderError(f"Reorder failed: {exc}") from exc
    finally:
        try:
            src.close()
        except Exception:
            pass

    logger.info("Reorder complete → %s", output_path)
    return output_path

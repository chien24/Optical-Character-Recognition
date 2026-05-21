"""Split PDF service — split a PDF by page ranges or into individual pages."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from pdf_tools.exceptions import SplitError
from .utils import open_pdf, save_pdf, get_output_path, ensure_output_dir, parse_page_ranges

logger = logging.getLogger(__name__)


def split_pdf(
    file_path: str,
    ranges: List[Tuple[int, int]],
    output_dir: Optional[str] = None,
) -> List[str]:
    """Split a PDF into multiple files, each containing the specified page range.

    Args:
        file_path: Absolute path to the source PDF.
        ranges: List of (start, end) tuples (1-indexed, inclusive).
                e.g. [(1, 3), (4, 7)] → two output files.
        output_dir: Directory for output files. Auto-created if None.

    Returns:
        List of absolute paths to the split output PDFs (same order as ranges).

    Raises:
        SplitError: if split fails for any reason.
    """
    if output_dir is None:
        output_dir = ensure_output_dir("splits")

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Splitting %s into %d range(s)", file_path, len(ranges))

    src = open_pdf(file_path)
    page_count = src.page_count
    output_paths: List[str] = []

    try:
        for idx, (start, end) in enumerate(ranges):
            if start < 1 or end > page_count or start > end:
                raise SplitError(
                    f"Range ({start}, {end}) invalid for {page_count}-page document."
                )

            # fitz uses 0-indexed pages
            fitz_range = list(range(start - 1, end))

            out_doc = fitz.open()
            out_doc.insert_pdf(src, from_page=start - 1, to_page=end - 1)

            out_path = os.path.join(output_dir, f"split_range{idx + 1}_{start}to{end}.pdf")
            save_pdf(out_doc, out_path)
            output_paths.append(out_path)
            logger.debug("Split range (%d-%d) → %s", start, end, out_path)

    except SplitError:
        raise
    except Exception as exc:
        raise SplitError(f"Split failed: {exc}") from exc
    finally:
        src.close()

    logger.info("Split complete: %d output files", len(output_paths))
    return output_paths


def split_pdf_by_ranges_str(
    file_path: str,
    ranges_str: str,
    output_dir: Optional[str] = None,
) -> List[str]:
    """Convenience wrapper: parse ranges string, then call split_pdf.

    Args:
        file_path: Absolute path to the source PDF.
        ranges_str: Range string like "1-3,5,7-9".
        output_dir: Optional output directory.

    Returns:
        List of output file paths.
    """
    src = open_pdf(file_path)
    page_count = src.page_count
    src.close()

    ranges = parse_page_ranges(ranges_str, page_count)
    return split_pdf(file_path, ranges, output_dir=output_dir)


def split_all_pages(
    file_path: str,
    output_dir: Optional[str] = None,
) -> List[str]:
    """Split a PDF into individual single-page PDFs.

    Args:
        file_path: Absolute path to the source PDF.
        output_dir: Directory for output files. Auto-created if None.

    Returns:
        List of absolute paths (one per page, ordered).

    Raises:
        SplitError: if any page extraction fails.
    """
    if output_dir is None:
        output_dir = ensure_output_dir("splits")

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Splitting %s into individual pages", file_path)

    src = open_pdf(file_path)
    page_count = src.page_count
    output_paths: List[str] = []

    try:
        for i in range(page_count):
            out_doc = fitz.open()
            out_doc.insert_pdf(src, from_page=i, to_page=i)
            out_path = os.path.join(output_dir, f"page_{i + 1:04d}.pdf")
            save_pdf(out_doc, out_path)
            output_paths.append(out_path)
            logger.debug("Extracted page %d → %s", i + 1, out_path)
    except Exception as exc:
        raise SplitError(f"split_all_pages failed: {exc}") from exc
    finally:
        src.close()

    logger.info("split_all_pages complete: %d pages", len(output_paths))
    return output_paths

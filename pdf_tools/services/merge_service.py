"""Merge PDF service — combine multiple PDF files into one."""

from __future__ import annotations

import logging
from typing import List

import fitz  # PyMuPDF

from pdf_tools.exceptions import MergeError
from .utils import open_pdf, save_pdf, get_output_path

logger = logging.getLogger(__name__)


def merge_pdfs(file_paths: List[str], output_path: str | None = None) -> str:
    """Merge multiple PDF files into a single PDF.

    Metadata from the first file is preserved in the output.

    Args:
        file_paths: Ordered list of absolute paths to source PDF files.
        output_path: Optional destination path. Auto-generated if None.

    Returns:
        Absolute path to the merged output PDF.

    Raises:
        MergeError: if merge fails for any reason.
        ValueError: if fewer than 2 files provided.
    """
    if not file_paths or len(file_paths) < 2:
        raise ValueError("At least 2 PDF files are required for merge.")

    if output_path is None:
        output_path = get_output_path("merged")

    logger.info("Merging %d PDFs → %s", len(file_paths), output_path)

    merged_doc = fitz.open()  # empty PDF

    try:
        # Preserve metadata from the first document
        first_meta: dict = {}

        for idx, path in enumerate(file_paths):
            src = open_pdf(path)  # validates PDF; raises InvalidPDFError on error
            if idx == 0:
                first_meta = src.metadata or {}
            merged_doc.insert_pdf(src)
            src.close()
            logger.debug("Inserted %s (%d pages)", path, src.page_count)

        # Restore metadata from first file into merged doc
        if first_meta:
            try:
                merged_doc.set_metadata(first_meta)
            except Exception:
                logger.warning("Could not set metadata on merged PDF; skipping.")

        save_pdf(merged_doc, output_path)

    except Exception as exc:
        merged_doc.close()
        if not isinstance(exc, (MergeError, ValueError)):
            raise MergeError(f"Merge failed: {exc}") from exc
        raise

    logger.info("Merge complete → %s", output_path)
    return output_path

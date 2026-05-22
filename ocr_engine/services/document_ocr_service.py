"""ocr_engine/services/document_ocr_service.py

Document-level OCR orchestrator — the single public entry point for running
OCR on any supported document type.

Architecture:
    This service is the ONLY component that knows both the OCR engine and the
    PDF rendering layer exist. It detects the input file type and dispatches
    to the appropriate processing path.

    Image files (png, jpg, jpeg, webp, bmp, tiff, tif):
        load_image(path) → PIL.Image → run_ocr_on_pil_image()

    PDF files (per-page, hybrid support):
        iter_pdf_pages() [generator — one page in memory at a time]:
            page has text layer  →  direct text extraction  (method="direct_text")
            page is scanned      →  render_page_to_pil() → run_ocr_on_pil_image()
                                                           (method="ocr")

Boundary contracts:
    • The OCR pipeline (run_ocr_on_pil_image) never receives a file path.
    • The PDF rendering layer (pdf_render_service) never performs model inference.
    • This orchestrator is the only component aware of both.

Settings consumed from Django settings:
    OCR_PDF_RENDER_DPI     (int, default 300)  — DPI for scanned page rendering
    OCR_PDF_TEXT_THRESHOLD (int, default 20)   — min chars to classify page as text-based
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from django.conf import settings

from .preprocess_service import load_image
from .ocr_pipeline import run_ocr_on_pil_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported file types
# ---------------------------------------------------------------------------

_SUPPORTED_IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif",
})
_SUPPORTED_PDF_EXTENSIONS = frozenset({".pdf"})
_ALL_SUPPORTED_EXTENSIONS = _SUPPORTED_IMAGE_EXTENSIONS | _SUPPORTED_PDF_EXTENSIONS


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class DocumentOCRError(Exception):
    """Base exception for document OCR errors."""


class UnsupportedFileTypeError(DocumentOCRError):
    """Raised when the file extension is not supported by the OCR pipeline."""


class CorruptedFileError(DocumentOCRError):
    """Raised when the file cannot be opened or appears corrupted."""


class EmptyDocumentError(DocumentOCRError):
    """Raised when the document has no pages or extractable content."""


class PDFRenderError(DocumentOCRError):
    """Raised when a specific PDF page fails to render to an image."""


class OCRPageError(DocumentOCRError):
    """Raised when the OCR model fails on a specific page (non-fatal by default)."""


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _get_pdf_render_dpi() -> int:
    return int(getattr(settings, "OCR_PDF_RENDER_DPI", 300))


def _get_pdf_text_threshold() -> int:
    return int(getattr(settings, "OCR_PDF_TEXT_THRESHOLD", 20))


# ---------------------------------------------------------------------------
# Private: image document handler
# ---------------------------------------------------------------------------

def _run_image_ocr(file_path: str, *, ocr_kwargs: Dict) -> Dict:
    """Run OCR on a single image file. Returns the standard result dict."""
    logger.info("Document type detected: image — %s", file_path)

    try:
        pil_img = load_image(file_path)
    except Exception as exc:
        raise CorruptedFileError(
            f"Cannot open image file {file_path!r}: {exc}"
        ) from exc

    result = run_ocr_on_pil_image(pil_img, **ocr_kwargs)

    pages_detail: List[Dict] = [
        {
            "page": 1,
            "method": "ocr",
            "text": result.get("raw_text", ""),
            "ocr_time": result.get("ocr_time"),
        }
    ]

    return {
        "raw_text": result.get("raw_text", ""),
        "corrected_text": result.get("corrected_text", ""),
        "ocr_time": result.get("ocr_time", 0.0),
        "correction_time": result.get("correction_time", 0.0),
        "total_time": result.get("total_time", 0.0),
        "page_count": 1,
        "file_type": "image",
        "pages_detail": pages_detail,
    }


# ---------------------------------------------------------------------------
# Private: PDF document handler (per-page, hybrid)
# ---------------------------------------------------------------------------

def _run_pdf_ocr(
    file_path: str,
    *,
    ocr_kwargs: Dict,
    pdf_render_dpi: int,
    pdf_text_threshold: int,
) -> Dict:
    """Run per-page OCR/extraction on a PDF file.

    Supports hybrid PDFs: each page is independently classified as text-based
    (direct extraction, no model inference) or scanned (rendered and OCR'd).
    Uses a generator so only one page image is in memory at a time.
    """
    from pdf_tools.services.pdf_render_service import iter_pdf_pages

    logger.info(
        "Document type detected: PDF — %s (DPI=%d, text_threshold=%d)",
        file_path, pdf_render_dpi, pdf_text_threshold,
    )

    total_start = time.perf_counter()
    pages_detail: List[Dict] = []
    all_text_parts: List[str] = []
    total_ocr_time = 0.0
    total_correction_time = 0.0
    page_count = 0

    # Open the generator — raises CorruptedFileError / InvalidPDFError on bad PDF
    try:
        page_gen = iter_pdf_pages(
            file_path,
            dpi=pdf_render_dpi,
            text_threshold=pdf_text_threshold,
        )
    except Exception as exc:
        raise CorruptedFileError(
            f"Cannot open or parse PDF {file_path!r}: {exc}"
        ) from exc

    for page_num, method, pil_img, direct_text in page_gen:
        page_count = page_num  # last seen = total after loop ends
        page_entry: Dict = {
            "page": page_num,
            "method": method,
            "text": "",
            "ocr_time": None,
        }

        if method == "direct_text":
            # ── Text-layer page: no model inference needed ──────────────────
            page_entry["text"] = direct_text
            all_text_parts.append(direct_text)
            logger.debug(
                "Page %d: direct_text extraction (%d chars)",
                page_num, len(direct_text),
            )

        else:
            # ── Scanned page: render already done by generator → OCR ────────
            try:
                ocr_result = run_ocr_on_pil_image(pil_img, **ocr_kwargs)
                page_text = (
                    ocr_result.get("corrected_text")
                    or ocr_result.get("raw_text", "")
                )
                page_ocr_time = ocr_result.get("ocr_time", 0.0)
                page_corr_time = ocr_result.get("correction_time", 0.0)

                page_entry["text"] = page_text
                page_entry["ocr_time"] = page_ocr_time
                all_text_parts.append(page_text)
                total_ocr_time += page_ocr_time
                total_correction_time += page_corr_time

                logger.debug(
                    "Page %d: OCR complete (%.3fs, %d chars)",
                    page_num, page_ocr_time, len(page_text),
                )

            except Exception as exc:
                # Log and continue — don't abort the whole document on one page failure
                logger.exception(
                    "OCR failed on page %d of %s — skipping page",
                    page_num, file_path,
                )
                page_entry["text"] = ""
                page_entry["error"] = str(exc)

        pages_detail.append(page_entry)

    if page_count == 0:
        raise EmptyDocumentError(f"PDF has no pages: {file_path!r}")

    full_text = "\n\n".join(part for part in all_text_parts if part)
    total_elapsed = time.perf_counter() - total_start

    logger.info(
        "PDF OCR complete: %d pages, %.3fs total (%d chars extracted)",
        page_count, total_elapsed, len(full_text),
    )

    return {
        "raw_text": full_text,
        # For PDF: correction is applied per page; full_text already contains corrected output
        "corrected_text": full_text,
        "ocr_time": total_ocr_time,
        "correction_time": total_correction_time,
        "total_time": total_elapsed,
        "page_count": page_count,
        "file_type": "pdf",
        "pages_detail": pages_detail,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_document_ocr(
    file_path: str,
    *,
    enhance_contrast: bool = False,
    denoise: bool = False,
    binarize: bool = False,
    enable_correction: Optional[bool] = None,
    ollama_model: Optional[str] = None,
    pdf_render_dpi: Optional[int] = None,
    pdf_text_threshold: Optional[int] = None,
) -> Dict:
    """Run OCR on any supported document — image or PDF.

    This is the **recommended public entry point** for the OCR pipeline.
    It handles both images and PDFs transparently, dispatching to the
    appropriate processing path based on file extension.

    Args:
        file_path:          Absolute path to the document to process.
        enhance_contrast:   Apply CLAHE contrast enhancement (image preprocessing).
        denoise:            Apply median-blur denoising (image preprocessing).
        binarize:           Apply Otsu binarization (image preprocessing).
        enable_correction:  Override ``settings.OCR_ENABLE_CORRECTION``.
                            Pass ``True``/``False`` to force; ``None`` reads settings.
        ollama_model:       Override ``settings.OLLAMA_MODEL`` for LLM correction.
        pdf_render_dpi:     DPI for PDF page rendering (default: ``settings.OCR_PDF_RENDER_DPI`` or 300).
        pdf_text_threshold: Min chars/page to treat as text-based (default: ``settings.OCR_PDF_TEXT_THRESHOLD`` or 20).

    Returns:
        Dict with keys:
            raw_text        (str)   — concatenated raw OCR / extracted text
            corrected_text  (str)   — after optional LLM correction
            ocr_time        (float) — total seconds in OCR model inference
            correction_time (float) — total seconds in LLM correction
            total_time      (float) — total wall-clock seconds
            page_count      (int)   — number of pages processed
            file_type       (str)   — "image" | "pdf"
            pages_detail    (list)  — per-page structured info:
                [
                    {
                        "page":     1,
                        "method":   "ocr" | "direct_text",
                        "text":     "...",
                        "ocr_time": 1.2,   # float | None (None for direct_text)
                        # "error": "..."   # only present if page failed
                    },
                    ...
                ]

    Raises:
        UnsupportedFileTypeError: file extension is not in the supported list.
        CorruptedFileError:       file cannot be opened or is corrupted.
        EmptyDocumentError:       document has no processable pages/content.
    """
    ext = Path(file_path).suffix.lower()
    logger.info("run_document_ocr called: file=%s ext=%s", file_path, ext)

    if ext not in _ALL_SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"File extension {ext!r} is not supported for OCR. "
            f"Supported extensions: {sorted(_ALL_SUPPORTED_EXTENSIONS)}"
        )

    ocr_kwargs = dict(
        enhance_contrast=enhance_contrast,
        denoise=denoise,
        binarize=binarize,
        enable_correction=enable_correction,
        ollama_model=ollama_model,
    )

    if ext in _SUPPORTED_PDF_EXTENSIONS:
        return _run_pdf_ocr(
            file_path,
            ocr_kwargs=ocr_kwargs,
            pdf_render_dpi=pdf_render_dpi if pdf_render_dpi is not None else _get_pdf_render_dpi(),
            pdf_text_threshold=pdf_text_threshold if pdf_text_threshold is not None else _get_pdf_text_threshold(),
        )
    else:
        return _run_image_ocr(file_path, ocr_kwargs=ocr_kwargs)

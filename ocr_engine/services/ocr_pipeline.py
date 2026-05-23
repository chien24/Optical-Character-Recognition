"""ocr_engine/services/ocr_pipeline.py

Single-image OCR pipeline — preprocessing → inference → postprocessing → correction.

Boundary:
    All functions accept PIL.Image objects.
    They do NOT access the filesystem.

Primary API:
    run_ocr_on_pil_image(pil_img, ...)  ← use this

Deprecated API (backward compat only):
    run_ocr_pipeline(image_path, ...)

For multi-page or mixed document (image / PDF), use:
    ocr_engine.services.document_ocr_service.run_document_ocr(file_path, ...)
"""
from __future__ import annotations

import logging
import time
import warnings
from typing import Dict, Optional

from django.conf import settings
from PIL import Image

from .preprocess_service import ImagePreprocessor, load_image, segment_lines
from .inference_service import extract_text_from_pil
from .correction_service import correct_with_ollama

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _postprocess_text(raw: str) -> str:
    """Collapse multiple spaces/tabs into a single space and strip edges."""
    import re
    text = re.sub(r"[ \t]+", " ", raw)
    return text.strip()


# ---------------------------------------------------------------------------
# Primary API — accepts PIL.Image (no filesystem access)
# ---------------------------------------------------------------------------

def run_ocr_on_pil_image(
    pil_img: Image.Image,
    *,
    enhance_contrast: bool = False,
    denoise: bool = False,
    binarize: bool = False,
    enable_correction: Optional[bool] = None,
    ollama_model: Optional[str] = None,
) -> Dict[str, object]:
    """Run the full single-image OCR pipeline on a PIL.Image.

    Pipeline: segment lines → preprocess → inference → postprocess → (optional) LLM correction.

    This is the **primary** single-image OCR entry point. It does not access
    the filesystem. For documents (PDF or any image file on disk), use
    :func:`~document_ocr_service.run_document_ocr` instead.

    Args:
        pil_img:           A PIL.Image to run OCR on (any mode).
        enhance_contrast:  Apply CLAHE contrast enhancement before inference.
        denoise:           Apply median-blur denoising before inference.
        binarize:          Apply Otsu binarization before inference.
        enable_correction: Override ``settings.OCR_ENABLE_CORRECTION``.
           Pass ``True`` / ``False`` to force; ``None`` reads settings.
        ollama_model:      Override ``settings.OLLAMA_MODEL`` for LLM correction.

    Returns:
        Dict with keys:
            raw_text        (str)   — text output directly from model
            corrected_text  (str)   — after optional LLM correction (== raw_text if disabled)
            ocr_time        (float) — seconds spent in model inference
            correction_time (float) — seconds spent in LLM correction (0.0 if disabled)
            total_time      (float) — total wall-clock seconds for this call
            expert_features (list)  — hand-crafted hybrid features for each line segment
            line_count      (int)   — number of line segments detected
    """
    total_start = time.perf_counter()

    # 1. Way C: Segment the multi-line image into individual horizontal lines
    lines = segment_lines(pil_img)

    preprocessor = ImagePreprocessor(
        enhance_contrast=enhance_contrast,
        denoise=denoise,
        binarize=binarize,
    )

    line_texts = []
    total_ocr_time = 0.0

    # 2. Run OCR line-by-line
    for i, line_crop in enumerate(lines, 1):
        try:
            line_text, ocr_time = extract_text_from_pil(line_crop, preprocessor)
            line_texts.append(line_text)
            total_ocr_time += ocr_time
        except Exception:
            logger.exception("OCR inference failed on line crop %d", i)
            # If there's only 1 line, let it bubble up, else continue with other lines
            if len(lines) == 1:
                raise

    # 3. Concatenate text of all line segments
    raw_text = "\n".join(line_texts)
    raw_text = _postprocess_text(raw_text)

    corr_time = 0.0
    corrected_text = raw_text

    if enable_correction is None:
        enable_correction = getattr(settings, "OCR_ENABLE_CORRECTION", False)

    if enable_correction:
        model_name = ollama_model or getattr(settings, "OLLAMA_MODEL", None)
        try:
            corrected_text, corr_time = correct_with_ollama(raw_text, model=model_name)
        except Exception:
            logger.exception("Ollama correction failed; returning raw text")
            corrected_text = raw_text
            corr_time = 0.0

    total_time = time.perf_counter() - total_start

    return {
        "raw_text": raw_text,
        "corrected_text": corrected_text,
        "ocr_time": float(total_ocr_time),
        "correction_time": float(corr_time),
        "total_time": float(total_time),
    }


# ---------------------------------------------------------------------------
# Deprecated API — kept for backward compatibility
# ---------------------------------------------------------------------------

def run_ocr_pipeline(
    image_path: str,
    *,
    enhance_contrast: bool = False,
    denoise: bool = False,
    binarize: bool = False,
    enable_correction: Optional[bool] = None,
    ollama_model: Optional[str] = None,
) -> Dict[str, object]:
    """[DEPRECATED] Run the OCR pipeline from a filesystem image path.

    .. deprecated::
        Use :func:`run_ocr_on_pil_image` with a PIL.Image loaded via
        :func:`~preprocess_service.load_image`.
        For documents (PDF or image files on disk), prefer
        :func:`~document_ocr_service.run_document_ocr`.

    Args:
        image_path: Absolute path to an image file (PNG, JPG, JPEG, WEBP, etc.).
        (other args same as :func:`run_ocr_on_pil_image`)

    Returns:
        Dict with same keys as :func:`run_ocr_on_pil_image`.
    """
    warnings.warn(
        "run_ocr_pipeline(image_path) is deprecated. "
        "Use run_ocr_on_pil_image(pil_img) or run_document_ocr(file_path) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    pil_img = load_image(image_path)
    return run_ocr_on_pil_image(
        pil_img,
        enhance_contrast=enhance_contrast,
        denoise=denoise,
        binarize=binarize,
        enable_correction=enable_correction,
        ollama_model=ollama_model,
    )

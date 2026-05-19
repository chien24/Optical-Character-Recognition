from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from django.conf import settings

from .preprocess_service import ImagePreprocessor
from .inference_service import extract_text_from_image
from .correction_service import correct_with_ollama

logger = logging.getLogger(__name__)


def _postprocess_text(raw: str) -> str:
    import re
    text = re.sub(r"[ \t]+", " ", raw)
    return text.strip()


def run_ocr_pipeline(
    image_path: str,
    *,
    enhance_contrast: bool = False,
    denoise: bool = False,
    binarize: bool = False,
    enable_correction: Optional[bool] = None,
    ollama_model: Optional[str] = None,
) -> Dict[str, object]:
    """Run full OCR pipeline for a single image path.

    Returns dict with keys: raw_text, corrected_text, ocr_time, correction_time, total_time
    """
    total_start = time.perf_counter()

    preprocessor = ImagePreprocessor(
        enhance_contrast=enhance_contrast, denoise=denoise, binarize=binarize
    )

    try:
        raw_text, ocr_time = extract_text_from_image(image_path, preprocessor)
    except Exception:
        logger.exception("OCR inference failed for %s", image_path)
        raise

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
        "ocr_time": float(ocr_time),
        "correction_time": float(corr_time),
        "total_time": float(total_time),
    }

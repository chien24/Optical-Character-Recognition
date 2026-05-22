"""ocr_engine/services/inference_service.py

Model inference functions for the custom PyTorch OCR model (ResNetEncoder).

Boundary:
    All functions accept PIL.Image objects (or preprocessed tensors).
    They do NOT access the filesystem.

Primary API:
    extract_text_from_pil(pil_img, preprocessor)  ← use this

Deprecated API (backward compat only):
    extract_text_from_image(image_path, preprocessor)
"""
from __future__ import annotations

import time
import warnings
from typing import Tuple

import torch
from PIL import Image

from .model_loader import get_model
from .preprocess_service import ImagePreprocessor, load_image
from .decode_service import greedy_decode, indices_to_string


# ---------------------------------------------------------------------------
# Primary API — accepts PIL.Image (no filesystem access)
# ---------------------------------------------------------------------------

def extract_text_from_pil(
    pil_img: Image.Image,
    preprocessor: ImagePreprocessor,
) -> Tuple[str, float]:
    """Run OCR inference on a PIL.Image and return (text, ocr_time).

    This is the **primary** inference function. It does not access the filesystem.
    Use it with a PIL.Image loaded by :func:`~preprocess_service.load_image` or
    rendered from a PDF page via ``pdf_render_service.render_page_to_pil``.

    Args:
        pil_img:      A PIL.Image object (any mode; converted internally by preprocessor).
        preprocessor: A configured :class:`~preprocess_service.ImagePreprocessor` instance.

    Returns:
        Tuple of (extracted_text: str, ocr_time_seconds: float).
    """
    bundle = get_model()
    model = bundle["model"]
    idx_to_char = bundle["idx_to_char"]
    sos_idx = bundle["sos_idx"]
    eos_idx = bundle["eos_idx"]
    pad_idx = bundle["pad_idx"]
    device = bundle["device"]

    tensor, _valid_w = preprocessor.preprocess_pil(pil_img)
    tensor = tensor.to(device)

    ocr_start = time.perf_counter()
    with torch.no_grad():
        pred_indices = greedy_decode(model, tensor, sos_idx, eos_idx)
    if device.type == "cuda":
        torch.cuda.synchronize()
    ocr_time = time.perf_counter() - ocr_start

    text = indices_to_string(pred_indices[0].tolist(), idx_to_char, eos_idx, pad_idx, sos_idx)
    return text, ocr_time


# ---------------------------------------------------------------------------
# Deprecated API — kept for backward compatibility
# ---------------------------------------------------------------------------

def extract_text_from_image(
    image_path: str,
    preprocessor: ImagePreprocessor,
    save_preprocessed: bool = False,
) -> Tuple[str, float]:
    """[DEPRECATED] Run OCR inference from a filesystem image path.

    .. deprecated::
        Use :func:`extract_text_from_pil` with a PIL.Image loaded via
        :func:`~preprocess_service.load_image` instead.
        Path-based inference couples filesystem concerns into the inference layer.

    Args:
        image_path:       Absolute path to an image file.
        preprocessor:     A configured :class:`~preprocess_service.ImagePreprocessor` instance.
        save_preprocessed: Unused; kept for API signature compatibility.

    Returns:
        Tuple of (extracted_text: str, ocr_time_seconds: float).
    """
    warnings.warn(
        "extract_text_from_image(image_path) is deprecated. "
        "Use extract_text_from_pil(pil_img) instead after loading with load_image().",
        DeprecationWarning,
        stacklevel=2,
    )
    pil_img = load_image(image_path)
    return extract_text_from_pil(pil_img, preprocessor)

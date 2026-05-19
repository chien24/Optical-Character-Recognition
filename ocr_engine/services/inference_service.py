from __future__ import annotations

import time
from typing import Tuple

import torch

from .model_loader import get_model
from .preprocess_service import ImagePreprocessor
from .decode_service import greedy_decode, indices_to_string


def extract_text_from_image(
    image_path: str,
    preprocessor: ImagePreprocessor,
    save_preprocessed: bool = False,
) -> Tuple[str, float]:
    bundle = get_model()
    model = bundle["model"]
    idx_to_char = bundle["idx_to_char"]
    sos_idx = bundle["sos_idx"]
    eos_idx = bundle["eos_idx"]
    pad_idx = bundle["pad_idx"]
    device = bundle["device"]

    prep_start = time.perf_counter()
    tensor, valid_w = preprocessor.preprocess(image_path)
    prep_time = time.perf_counter() - prep_start

    tensor = tensor.to(device)

    ocr_start = time.perf_counter()
    with torch.no_grad():
        pred_indices = greedy_decode(model, tensor, sos_idx, eos_idx)
    if device.type == "cuda":
        torch.cuda.synchronize()
    ocr_time = time.perf_counter() - ocr_start

    text = indices_to_string(pred_indices[0].tolist(), idx_to_char, eos_idx, pad_idx, sos_idx)
    return text, ocr_time

"""Singleton model loader for the OCR PyTorch model.

Loads checkpoint once, builds vocab mappings and returns a cached bundle
that other services can reuse.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import torch
from django.conf import settings

logger = logging.getLogger(__name__)

_MODEL_BUNDLE: Optional[Dict[str, Any]] = None


def _resolve_paths() -> Dict[str, str]:
    model_path = getattr(settings, "OCR_MODEL_PATH", None)
    vocab_path = getattr(settings, "OCR_VOCAB_PATH", None)

    base = Path(settings.BASE_DIR)

    if not model_path or not Path(model_path).exists():
        cand = base / "ocr_engine" / "services" / "engines" / "best_model.pth"
        if cand.exists():
            model_path = str(cand)
        else:
            fallback = base / "best_model.pth"
            model_path = str(fallback)

    if not vocab_path or not Path(vocab_path).exists():
        cand_v = base / "ocr_engine" / "services" / "engines" / "vocab.txt"
        if cand_v.exists():
            vocab_path = str(cand_v)
        else:
            fallback_v = base / "vocab.txt"
            vocab_path = str(fallback_v)

    return {"model_path": model_path, "vocab_path": vocab_path}


def initialize_model(force: bool = False) -> Dict[str, Any]:
    """Load the model and cache the result. If already loaded, returns cached bundle.

    The bundle contains: model, char_to_idx, idx_to_char, sos_idx, eos_idx, pad_idx, unk_idx, device
    """
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is not None and not force:
        return _MODEL_BUNDLE

    paths = _resolve_paths()
    model_path = paths["model_path"]
    vocab_path = paths["vocab_path"]

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"OCR model not found at {model_path}")

    use_gpu = getattr(settings, "OCR_USE_GPU", None)
    if use_gpu is True:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    elif use_gpu is False:
        device = torch.device("cpu")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Import model classes lazily to avoid heavy imports at module import time
    from ..torch_models.ocr_model import OCRModel, _infer_vocab_size_from_state, PAD_TOKEN, SOS_TOKEN, EOS_TOKEN, UNK_TOKEN  # type: ignore

    logger.info("Loading OCR checkpoint %s on device=%s", model_path, device)

    ckpt = torch.load(model_path, map_location=device)

    if "model_state" in ckpt:
        state_dict = ckpt["model_state"]
    elif "model_state_dict" in ckpt:
        state_dict = ckpt["model_state_dict"]
    else:
        state_dict = ckpt

    # Build vocab
    char_to_idx = {}
    idx_to_char = {}

    if vocab_path and os.path.exists(vocab_path):
        with open(vocab_path, encoding="utf-8") as f:
            lines_v = [ln.rstrip("\n") for ln in f.readlines()]
        chars = list(lines_v[0]) if len(lines_v) == 1 else lines_v
        vocab_list = [PAD_TOKEN, SOS_TOKEN, EOS_TOKEN, UNK_TOKEN] + sorted(set(chars))
        char_to_idx = {c: i for i, c in enumerate(vocab_list)}
        idx_to_char = {i: c for c, i in char_to_idx.items()}
        vocab_size = len(vocab_list)
        logger.info("Vocab loaded from %s (%d tokens)", vocab_path, vocab_size)

    elif "vocab" in ckpt:
        vocab_list = ckpt["vocab"]
        char_to_idx = {c: i for i, c in enumerate(vocab_list)}
        idx_to_char = {i: c for c, i in char_to_idx.items()}
        vocab_size = len(vocab_list)
        logger.info("Vocab loaded from checkpoint['vocab'] (%d tokens)", vocab_size)

    elif "char_to_idx" in ckpt:
        char_to_idx = ckpt["char_to_idx"]
        idx_to_char = {i: c for c, i in char_to_idx.items()}
        vocab_size = len(char_to_idx)
        logger.info("Vocab loaded from checkpoint['char_to_idx'] (%d tokens)", vocab_size)

    else:
        vocab_size = _infer_vocab_size_from_state(state_dict)
        logger.warning("No vocab found in checkpoint; inferred vocab_size=%d", vocab_size)
        n_chars = vocab_size - 4
        dummy = [chr(0xE000 + i) for i in range(n_chars)]
        vocab_list = [PAD_TOKEN, SOS_TOKEN, EOS_TOKEN, UNK_TOKEN] + dummy
        char_to_idx = {c: i for i, c in enumerate(vocab_list)}
        idx_to_char = {i: c for c, i in char_to_idx.items()}

    pad_idx = char_to_idx.get(PAD_TOKEN, 0)
    sos_idx = char_to_idx.get(SOS_TOKEN, 1)
    eos_idx = char_to_idx.get(EOS_TOKEN, 2)
    unk_idx = char_to_idx.get(UNK_TOKEN, 3)

    model = OCRModel(
        vocab_size=vocab_size,
        pad_idx=pad_idx,
    ).to(device)

    model.load_state_dict(state_dict, strict=True)
    model.eval()

    bundle = {
        "model": model,
        "char_to_idx": char_to_idx,
        "idx_to_char": idx_to_char,
        "sos_idx": sos_idx,
        "eos_idx": eos_idx,
        "pad_idx": pad_idx,
        "unk_idx": unk_idx,
        "device": device,
        "model_path": model_path,
        "vocab_path": vocab_path,
    }

    _MODEL_BUNDLE = bundle
    logger.info("OCR model loaded and cached (%d params)", sum(p.numel() for p in model.parameters()))
    return bundle


def get_model() -> Dict[str, Any]:
    """Return the cached model bundle; will initialize if not loaded."""
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is None:
        return initialize_model()
    return _MODEL_BUNDLE

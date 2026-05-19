from __future__ import annotations

import json
import logging
import time
from typing import List, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


CORRECTION_SYSTEM_PROMPT = """Bạn là trợ lý chuyên sửa lỗi OCR văn bản tiếng Việt.
Nhiệm vụ: Sửa lỗi nhận dạng ký tự, lỗi dấu thanh tiếng Việt, lỗi ghép từ sai.
Quy tắc:
- Chỉ sửa lỗi OCR, KHÔNG thêm nội dung mới
- Giữ nguyên cấu trúc đoạn văn
- Trả về văn bản đã sửa, không giải thích
- Không thêm bất kỳ tiêu đề hay chú thích nào"""

CORRECTION_USER_TEMPLATE = """Sửa lỗi OCR trong đoạn văn tiếng Việt sau:

{text}

Văn bản đã sửa:"""


def _base_url() -> str:
    return getattr(settings, "OLLAMA_URL", "http://localhost:11434")


def is_ollama_available() -> bool:
    try:
        r = requests.get(f"{_base_url()}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def list_ollama_models() -> List[str]:
    try:
        r = requests.get(f"{_base_url()}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def pull_ollama_model(model: str) -> bool:
    logger.info("Pulling Ollama model %s", model)
    try:
        with requests.post(f"{_base_url()}/api/pull", json={"name": model}, stream=True, timeout=600) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    data = json.loads(line)
                    status = data.get("status", "")
                    logger.debug("ollama pull: %s", status)
        return True
    except Exception as e:
        logger.exception("Failed to pull model %s: %s", model, e)
        return False


def correct_with_ollama(text: str, model: str | None = None, max_chunk_chars: int = 800) -> Tuple[str, float]:
    if not text.strip():
        return text, 0.0

    base_url = _base_url()
    model = model or getattr(settings, "OLLAMA_MODEL", "qwen2.5:0.5b")

    if not is_ollama_available():
        logger.warning("Ollama not available at %s", base_url)
        return text, 0.0

    available = list_ollama_models()
    model_names = [m.split(":")[0] for m in available]
    query_name = model.split(":")[0]

    if query_name not in model_names and model not in available:
        ok = pull_ollama_model(model)
        if not ok:
            logger.warning("Failed to pull Ollama model %s; returning raw text", model)
            return text, 0.0

    # Chunk by sentences
    import re

    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    chunks: List[str] = []
    cur_chunk: List[str] = []
    cur_len = 0

    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        if cur_len + len(s) > max_chunk_chars and cur_chunk:
            chunks.append(" ".join(cur_chunk))
            cur_chunk = [s]
            cur_len = len(s)
        else:
            cur_chunk.append(s)
            cur_len += len(s) + 1

    if cur_chunk:
        chunks.append(" ".join(cur_chunk))

    corrected_parts: List[str] = []
    corr_start = time.perf_counter()

    for chunk in chunks:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
                {"role": "user", "content": CORRECTION_USER_TEMPLATE.format(text=chunk)},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9, "repeat_penalty": 1.1},
        }
        try:
            t0 = time.perf_counter()
            r = requests.post(f"{base_url}/api/chat", json=payload, timeout=120)
            r.raise_for_status()
            elapsed = time.perf_counter() - t0
            corrected = r.json()["message"]["content"].strip()
            if len(corrected) > len(chunk) * 2.5:
                logger.warning("Ollama hallucination detected; keeping original chunk")
                corrected_parts.append(chunk)
            else:
                logger.info("Chunk corrected in %.1fs", elapsed)
                corrected_parts.append(corrected)
        except Exception:
            logger.exception("Ollama correction failed for a chunk; keeping original")
            corrected_parts.append(chunk)

    corr_time = time.perf_counter() - corr_start
    corrected_text = "\n\n".join(corrected_parts)
    return corrected_text, corr_time

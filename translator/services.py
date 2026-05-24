"""
Translation service layer using Google Translate's public web endpoint.

This implementation does not require an API key. It uses the same lightweight
endpoint commonly used by the Google Translate web client, so it is suitable
for local/demo use but can be rate-limited by Google.
"""

from __future__ import annotations

import html
import logging
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
MAX_CHARS_PER_REQUEST = 4500
REQUEST_TIMEOUT_SECONDS = 10
ERROR_PREFIX = "[Translation error]"


def translate_text(
    text: str,
    target_language: str = "vi",
    source_language: Optional[str] = None,
) -> str:
    """Translate text with Google Translate's free public endpoint."""
    if not text or not text.strip():
        return ""

    source_language = _normalize_source_language(source_language)
    target_language = _normalize_target_language(target_language)

    if source_language == target_language:
        return text

    try:
        chunks = _chunk_text(text, MAX_CHARS_PER_REQUEST)
        translated_chunks = [
            _translate_chunk(chunk, target_language, source_language)
            for chunk in chunks
        ]
        return "".join(translated_chunks)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Google Translate free endpoint error: %s", exc)
        return f"{ERROR_PREFIX} {exc}"


def detect_language(text: str) -> Optional[str]:
    """Detect the source language using the free translation endpoint."""
    if not text or not text.strip():
        return None

    try:
        data = _request_translation(text[:MAX_CHARS_PER_REQUEST], "en", "auto")
        language = _extract_detected_language(data)
        return language or None
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Language detection error: %s", exc)
        return None


def _translate_chunk(
    text: str,
    target_language: str,
    source_language: str,
) -> str:
    data = _request_translation(text, target_language, source_language)
    translated = _extract_translated_text(data)
    if not translated and text.strip():
        raise RuntimeError("Google Translate returned an empty response.")
    return translated


def _request_translation(
    text: str,
    target_language: str,
    source_language: str,
) -> list:
    url = getattr(settings, "GOOGLE_TRANSLATE_FREE_URL", GOOGLE_TRANSLATE_URL)
    timeout = getattr(
        settings,
        "GOOGLE_TRANSLATE_TIMEOUT_SECONDS",
        REQUEST_TIMEOUT_SECONDS,
    )
    response = requests.get(
        url,
        params={
            "client": "gtx",
            "sl": source_language,
            "tl": target_language,
            "dt": "t",
            "q": text,
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _extract_translated_text(data: list) -> str:
    if not data or not isinstance(data[0], list):
        return ""

    translated_segments = []
    for segment in data[0]:
        if isinstance(segment, list) and segment:
            translated_segments.append(segment[0] or "")

    return html.unescape("".join(translated_segments))


def _extract_detected_language(data: list) -> str:
    if len(data) > 2 and isinstance(data[2], str):
        return data[2]
    return ""


def _normalize_source_language(language: Optional[str]) -> str:
    if not language:
        return "auto"
    language = language.strip().lower()
    return language or "auto"


def _normalize_target_language(language: Optional[str]) -> str:
    if not language:
        return "vi"
    language = language.strip().lower()
    return language or "vi"


def _chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(line) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_line(line, max_chars))
            continue

        if len(current) + len(line) > max_chars:
            chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)

    return chunks


def _split_long_line(line: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for word in line.split(" "):
        separator = " " if current else ""
        candidate = f"{current}{separator}{word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(word) > max_chars:
            chunks.append(word[:max_chars])
            word = word[max_chars:]
        current = word

    if current:
        chunks.append(current)

    return chunks

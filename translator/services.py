"""
translator/services.py

Translation service layer using Google Cloud Translation API v2.

Follows the architecture boundary:
  - translator/views.py calls translate_text() from this module
  - This module handles provider setup, error handling, and caching
  - No translation logic leaks into views.py

Dependencies
------------
    pip install google-cloud-translate

Configuration (settings.py)
----------------------------
    GOOGLE_TRANSLATE_API_KEY = "YOUR_API_KEY"   # recommended
    # OR set GOOGLE_APPLICATION_CREDENTIALS env variable pointing to JSON key file

Usage
-----
    from translator.services import translate_text
    translated = translate_text("Hello world", target_language="vi")
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Return a cached Google Cloud Translation v2 client.

    Tries API key from settings first, then falls back to
    Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS).
    """
    global _client
    if _client is not None:
        return _client

    try:
        from google.cloud import translate_v2 as translate  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-translate is not installed. "
            "Install it with: pip install google-cloud-translate"
        ) from exc

    api_key: Optional[str] = getattr(settings, "GOOGLE_TRANSLATE_API_KEY", None)

    if api_key:
        # Use API key authentication (simplest for development)
        import google.auth.credentials  # type: ignore
        from google.oauth2 import service_account  # type: ignore — not always needed

        # google-cloud-translate v2 with API key requires building the client manually
        import googleapiclient.discovery  # type: ignore
        # Fallback: use the translate_v2 client with api_key parameter if available
        try:
            _client = translate.Client(client_options={"api_key": api_key})
        except TypeError:
            # Older versions don't support client_options; set key via env
            import os
            os.environ.setdefault("GOOGLE_API_KEY", api_key)
            _client = translate.Client()
    else:
        # Application Default Credentials
        _client = translate.Client()

    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_text(
    text: str,
    target_language: str = "vi",
    source_language: Optional[str] = None,
) -> str:
    """Translate *text* to *target_language* using Google Cloud Translation.

    Args:
        text:            The source text to translate.
        target_language: BCP-47 language code for the output language,
                         e.g. ``"vi"``, ``"en"``, ``"zh"``, ``"ja"``.
        source_language: BCP-47 source language code.  When ``None`` (default)
                         Google will auto-detect the source language.

    Returns:
        Translated text string on success.
        An empty string if ``text`` is blank.
        An error message string (prefixed with ``"[Translation error]"``) on failure.

    Notes:
        This function never raises — errors are logged and returned as a
        human-readable message so the view can still render gracefully.
    """
    if not text or not text.strip():
        return ""

    try:
        client = _get_client()
    except RuntimeError as exc:
        logger.error("Translation client unavailable: %s", exc)
        return f"[Translation error] {exc}"

    try:
        kwargs: dict = {"target_language": target_language}
        if source_language and source_language != "auto":
            kwargs["source_language"] = source_language

        result = client.translate(text, **kwargs)
        translated: str = result.get("translatedText", "")

        # Google HTML-encodes some characters in the response; decode them
        translated = _html_unescape(translated)
        logger.info(
            "Translated %d chars → %s (detected source: %s)",
            len(text),
            target_language,
            result.get("detectedSourceLanguage", source_language or "auto"),
        )
        return translated

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Google Translate API error: %s", exc)
        return f"[Translation error] {exc}"


def detect_language(text: str) -> Optional[str]:
    """Detect the language of *text*.

    Args:
        text: The text to detect language for.

    Returns:
        BCP-47 language code (e.g. ``"en"``), or ``None`` on failure.
    """
    if not text or not text.strip():
        return None
    try:
        client = _get_client()
        result = client.detect_language(text)
        return result.get("language")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Language detection error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html_unescape(text: str) -> str:
    """Unescape HTML entities that Google Translate may return."""
    import html
    return html.unescape(text)

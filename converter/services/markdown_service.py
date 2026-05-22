"""
converter/services/markdown_service.py

Converters that involve Markdown content.

Registered pairs
----------------
- md → txt   (MarkdownToTextConverter)  — strips Markdown syntax to plain text
- md → pdf   (MarkdownToPdfConverter)  — converts via HTML intermediary using WeasyPrint
               (WeasyPrint is already in requirements.txt)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .base import BaseConverter
from .exceptions import ConversionFailedError, FileMissingError
from .registry import registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Markdown → Plain Text
# ---------------------------------------------------------------------------


class MarkdownToTextConverter(BaseConverter):
    """Strip Markdown syntax and produce a clean plain-text file."""

    source_format = "md"
    target_format = "txt"

    # Patterns to strip common Markdown syntax.
    _PATTERNS = [
        (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),          # headings
        (re.compile(r"\*\*(.+?)\*\*"), r"\1"),                    # bold **
        (re.compile(r"\*(.+?)\*"), r"\1"),                         # italic *
        (re.compile(r"__(.+?)__"), r"\1"),                         # bold __
        (re.compile(r"_(.+?)_"), r"\1"),                           # italic _
        (re.compile(r"`{3}[\s\S]*?`{3}", re.MULTILINE), ""),      # code blocks
        (re.compile(r"`(.+?)`"), r"\1"),                           # inline code
        (re.compile(r"!\[.*?\]\(.*?\)"), ""),                      # images
        (re.compile(r"\[(.+?)\]\(.*?\)"), r"\1"),                  # links
        (re.compile(r"^[-*+]\s+", re.MULTILINE), ""),             # unordered lists
        (re.compile(r"^\d+\.\s+", re.MULTILINE), ""),             # ordered lists
        (re.compile(r"^>{1,}\s?", re.MULTILINE), ""),             # blockquotes
        (re.compile(r"^-{3,}$", re.MULTILINE), ""),               # horizontal rules
        (re.compile(r"^\|.*\|$", re.MULTILINE), ""),              # tables
        (re.compile(r"\n{3,}"), "\n\n"),                           # collapse blank lines
    ]

    def convert(self, input_path: Path, output_path: Path) -> Path:
        if not input_path.exists():
            raise FileMissingError(f"Source Markdown file not found: {input_path}")
        self._log_start(input_path, output_path)
        self._ensure_parent(output_path)

        try:
            content = input_path.read_text(encoding="utf-8")
            for pattern, repl in self._PATTERNS:
                content = pattern.sub(repl, content)
            output_path.write_text(content.strip(), encoding="utf-8")
        except Exception as exc:
            raise ConversionFailedError(
                f"Failed to convert '{input_path.name}' to plain text: {exc}"
            ) from exc

        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Markdown → PDF
# ---------------------------------------------------------------------------


class MarkdownToPdfConverter(BaseConverter):
    """Convert a Markdown file to PDF via HTML using WeasyPrint.

    Pipeline: .md → HTML string → WeasyPrint → .pdf
    WeasyPrint is already listed in requirements.txt.
    """

    source_format = "md"
    target_format = "pdf"

    _CSS = """
        body { font-family: sans-serif; font-size: 12pt; line-height: 1.6;
               margin: 2cm; color: #333; }
        h1, h2, h3 { color: #111; margin-top: 1.2em; }
        pre, code { background: #f5f5f5; padding: 2px 4px; font-size: 0.9em; }
        blockquote { border-left: 3px solid #ccc; padding-left: 1em; color: #666; }
        a { color: #0066cc; }
    """

    def convert(self, input_path: Path, output_path: Path) -> Path:
        if not input_path.exists():
            raise FileMissingError(f"Source Markdown file not found: {input_path}")
        self._log_start(input_path, output_path)
        self._ensure_parent(output_path)

        try:
            import markdown as md_lib  # type: ignore
        except ImportError:
            # Fallback: use basic conversion if markdown package not installed.
            logger.warning(
                "The 'markdown' package is not installed; "
                "falling back to basic HTML wrapping."
            )
            md_lib = None

        try:
            from weasyprint import CSS, HTML  # type: ignore
        except ImportError as exc:
            raise ConversionFailedError(
                "WeasyPrint is required for Markdown→PDF conversion. "
                "Install it with: pip install WeasyPrint"
            ) from exc

        try:
            raw = input_path.read_text(encoding="utf-8")
            if md_lib is not None:
                body_html = md_lib.markdown(
                    raw,
                    extensions=["fenced_code", "tables", "nl2br"],
                )
            else:
                # Minimal escaping + wrap in <pre> as a last resort.
                escaped = raw.replace("&", "&amp;").replace("<", "&lt;")
                body_html = f"<pre>{escaped}</pre>"

            html_doc = (
                "<!DOCTYPE html><html><head>"
                "<meta charset='utf-8'>"
                "</head><body>"
                f"{body_html}"
                "</body></html>"
            )
            HTML(string=html_doc).write_pdf(
                str(output_path),
                stylesheets=[CSS(string=self._CSS)],
            )
        except Exception as exc:
            raise ConversionFailedError(
                f"Failed to convert '{input_path.name}' to PDF: {exc}"
            ) from exc

        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

registry.register(MarkdownToTextConverter())
registry.register(MarkdownToPdfConverter())

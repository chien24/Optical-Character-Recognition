"""
converter/services/pdf_service.py

Converters that produce or consume PDF files using PyMuPDF (fitz).

Registered pairs
----------------
- pdf  → txt   (PdfToTextConverter)
- pdf  → md    (PdfToMarkdownConverter)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

try:
    import fitz  # PyMuPDF
    _FITZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore
    _FITZ_AVAILABLE = False
    import logging as _log
    _log.getLogger(__name__).warning(
        "PyMuPDF (fitz) is not installed; PDF conversions will be unavailable. "
        "Install with: pip install PyMuPDF"
    )

from .base import BaseConverter
from .exceptions import ConversionFailedError, CorruptedFileError, FileMissingError
from .registry import registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PDF → Text
# ---------------------------------------------------------------------------


class PdfToTextConverter(BaseConverter):
    """Extract plain text from a PDF, preserving page order."""

    source_format = "pdf"
    target_format = "txt"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        """Extract text from every page and write to a UTF-8 text file.

        Args:
            input_path:  Path to the source PDF.
            output_path: Path where the .txt file will be written.

        Returns:
            Resolved ``output_path``.

        Raises:
            FileMissingError:    If ``input_path`` does not exist.
            CorruptedFileError:  If PyMuPDF cannot open the PDF.
            ConversionFailedError: On any other processing error.
        """
        self._check_exists(input_path)
        if not _FITZ_AVAILABLE:
            raise ConversionFailedError(
                "PyMuPDF is not installed. Install with: pip install PyMuPDF"
            )
        self._log_start(input_path, output_path)
        self._ensure_parent(output_path)

        try:
            doc = fitz.open(str(input_path))
        except Exception as exc:
            raise CorruptedFileError(
                f"Cannot open PDF '{input_path.name}': {exc}"
            ) from exc

        try:
            pages: List[str] = []
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text")
                pages.append(f"--- Page {page_num} ---\n{text}")
            full_text = "\n\n".join(pages)
        except Exception as exc:
            raise ConversionFailedError(
                f"Failed to extract text from '{input_path.name}': {exc}"
            ) from exc
        finally:
            doc.close()

        output_path.write_text(full_text, encoding="utf-8")
        self._log_done(output_path)
        return output_path

    # ------------------------------------------------------------------

    @staticmethod
    def _check_exists(path: Path) -> None:
        if not path.exists():
            raise FileMissingError(f"Source file not found: {path}")


# ---------------------------------------------------------------------------
# PDF → Markdown
# ---------------------------------------------------------------------------


class PdfToMarkdownConverter(BaseConverter):
    """Convert a PDF to basic Markdown, inferring headings from font size."""

    source_format = "pdf"
    target_format = "md"

    # Font-size thresholds for heading detection.
    _H1_SIZE = 20.0
    _H2_SIZE = 16.0
    _H3_SIZE = 13.0

    def convert(self, input_path: Path, output_path: Path) -> Path:
        """Extract structured text from the PDF and emit Markdown.

        Args:
            input_path:  Path to the source PDF.
            output_path: Path where the .md file will be written.

        Returns:
            Resolved ``output_path``.

        Raises:
            FileMissingError:      Source file missing.
            CorruptedFileError:    PDF cannot be opened.
            ConversionFailedError: Processing failed.
        """
        if not input_path.exists():
            raise FileMissingError(f"Source file not found: {input_path}")
        if not _FITZ_AVAILABLE:
            raise ConversionFailedError(
                "PyMuPDF is not installed. Install with: pip install PyMuPDF"
            )
        self._log_start(input_path, output_path)
        self._ensure_parent(output_path)

        try:
            doc = fitz.open(str(input_path))
        except Exception as exc:
            raise CorruptedFileError(
                f"Cannot open PDF '{input_path.name}': {exc}"
            ) from exc

        try:
            md_parts: List[str] = []
            for page_num, page in enumerate(doc, start=1):
                md_parts.append(f"\n---\n*Page {page_num}*\n")
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block.get("type") != 0:  # 0 = text block
                        continue
                    for line in block.get("lines", []):
                        line_text_parts: List[str] = []
                        max_font_size = 0.0
                        for span in line.get("spans", []):
                            span_text = span.get("text", "").strip()
                            if span_text:
                                line_text_parts.append(span_text)
                                size = span.get("size", 0.0)
                                if size > max_font_size:
                                    max_font_size = size

                        line_text = " ".join(line_text_parts).strip()
                        if not line_text:
                            continue

                        md_parts.append(
                            self._format_line(line_text, max_font_size)
                        )
        except Exception as exc:
            raise ConversionFailedError(
                f"Failed to convert '{input_path.name}' to Markdown: {exc}"
            ) from exc
        finally:
            doc.close()

        output_path.write_text("\n".join(md_parts), encoding="utf-8")
        self._log_done(output_path)
        return output_path

    def _format_line(self, text: str, font_size: float) -> str:
        """Return the Markdown-formatted string for a single text line."""
        text = self._clean(text)
        if font_size >= self._H1_SIZE:
            return f"# {text}"
        if font_size >= self._H2_SIZE:
            return f"## {text}"
        if font_size >= self._H3_SIZE:
            return f"### {text}"
        return text

    @staticmethod
    def _clean(text: str) -> str:
        """Strip excessive whitespace."""
        return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Register all converters in this module
# ---------------------------------------------------------------------------

registry.register(PdfToTextConverter())
registry.register(PdfToMarkdownConverter())

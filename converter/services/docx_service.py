"""
converter/services/docx_service.py

Converters involving DOCX files using LibreOffice headless.

LibreOffice is a **system dependency** — it must be installed separately
and available on PATH (or configured via settings.LIBREOFFICE_PATH).

Registered pairs
----------------
- docx → pdf   (DocxToPdfConverter)
- docx → txt   (DocxToTextConverter)  via LibreOffice --convert-to txt
- docx → md    (DocxToMarkdownConverter)  txt output + lightweight md wrapping
- pdf  → docx  (PdfToDocxConverter)   via LibreOffice
- txt  → pdf   (TxtToPdfConverter)    via LibreOffice
- txt  → docx  (TxtToDocxConverter)   via LibreOffice
- md   → pdf   (MdToPdfConverter)     via LibreOffice (txt intermediate)
- md   → docx  (MdToDocxConverter)    via LibreOffice (txt intermediate)
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from .base import BaseConverter
from .exceptions import ConversionFailedError, FileMissingError
from .registry import registry

logger = logging.getLogger(__name__)

# Allow the LibreOffice executable path to be configured in Django settings.
_LIBREOFFICE_BIN: str = getattr(settings, "LIBREOFFICE_PATH", "soffice")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _run_libreoffice(input_path: Path, target_ext: str, tmp_dir: Path) -> Path:
    """Run LibreOffice headless conversion and return the output path.

    Args:
        input_path: Source file path.
        target_ext: Target extension e.g. "pdf", "txt", "docx".
        tmp_dir: Temporary directory for LibreOffice output.

    Returns:
        Path to the converted file inside tmp_dir.

    Raises:
        ConversionFailedError: On any LibreOffice failure.
    """
    try:
        result = subprocess.run(
            [
                _LIBREOFFICE_BIN,
                "--headless",
                "--convert-to",
                target_ext,
                str(input_path),
                "--outdir",
                str(tmp_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise ConversionFailedError(
            f"LibreOffice not found at '{_LIBREOFFICE_BIN}'. "
            "Install LibreOffice and ensure it is on PATH, or set "
            "settings.LIBREOFFICE_PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ConversionFailedError(
            f"LibreOffice timed out converting '{input_path.name}'."
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ConversionFailedError(
            f"LibreOffice exited with code {result.returncode} "
            f"for '{input_path.name}': {stderr}"
        )

    expected = tmp_dir / (input_path.stem + f".{target_ext}")
    if not expected.exists():
        # LibreOffice may use a slightly different stem; scan the dir
        candidates = list(tmp_dir.glob(f"*.{target_ext}"))
        if not candidates:
            raise ConversionFailedError(
                f"LibreOffice did not produce a .{target_ext} file "
                f"in the temp directory for '{input_path.name}'."
            )
        expected = candidates[0]

    return expected


def _libreoffice_convert(input_path: Path, output_path: Path, target_ext: str) -> Path:
    """Full pipeline: copy input → LibreOffice → move output."""
    if not input_path.exists():
        raise FileMissingError(f"Source file not found: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="conv_lo_") as tmp:
        tmp_dir = Path(tmp)
        # Copy source into tmp so LibreOffice has a clean working copy
        tmp_input = tmp_dir / input_path.name
        shutil.copy2(str(input_path), str(tmp_input))
        result_path = _run_libreoffice(tmp_input, target_ext, tmp_dir)
        shutil.move(str(result_path), str(output_path))

    return output_path


# ---------------------------------------------------------------------------
# DOCX → PDF
# ---------------------------------------------------------------------------

class DocxToPdfConverter(BaseConverter):
    """Convert DOCX → PDF via LibreOffice headless."""

    source_format = "docx"
    target_format = "pdf"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        self._log_start(input_path, output_path)
        result = _libreoffice_convert(input_path, output_path, "pdf")
        self._log_done(output_path)
        return result


# ---------------------------------------------------------------------------
# DOCX → TXT
# ---------------------------------------------------------------------------

class DocxToTextConverter(BaseConverter):
    """Convert DOCX → TXT via LibreOffice headless."""

    source_format = "docx"
    target_format = "txt"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        self._log_start(input_path, output_path)
        result = _libreoffice_convert(input_path, output_path, "txt")
        self._log_done(output_path)
        return result


# ---------------------------------------------------------------------------
# DOCX → MD
# ---------------------------------------------------------------------------

class DocxToMarkdownConverter(BaseConverter):
    """Convert DOCX → Markdown: first extract plain text via LibreOffice,
    then perform minimal Markdown formatting."""

    source_format = "docx"
    target_format = "md"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        self._log_start(input_path, output_path)
        if not input_path.exists():
            raise FileMissingError(f"Source file not found: {input_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="conv_docx_md_") as tmp:
            tmp_dir = Path(tmp)
            tmp_input = tmp_dir / input_path.name
            shutil.copy2(str(input_path), str(tmp_input))
            # Step 1: docx → txt
            txt_path = _run_libreoffice(tmp_input, "txt", tmp_dir)
            text = txt_path.read_text(encoding="utf-8", errors="replace")

        # Step 2: wrap as minimal Markdown
        lines = text.splitlines()
        md_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                md_lines.append("")
            else:
                md_lines.append(stripped)

        output_path.write_text("\n".join(md_lines), encoding="utf-8")
        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# PDF → DOCX
# ---------------------------------------------------------------------------

class PdfToDocxConverter(BaseConverter):
    """Convert PDF → DOCX via LibreOffice headless."""

    source_format = "pdf"
    target_format = "docx"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        self._log_start(input_path, output_path)
        result = _libreoffice_convert(input_path, output_path, "docx")
        self._log_done(output_path)
        return result


# ---------------------------------------------------------------------------
# TXT → PDF
# ---------------------------------------------------------------------------

class TxtToPdfConverter(BaseConverter):
    """Convert TXT → PDF via LibreOffice headless."""

    source_format = "txt"
    target_format = "pdf"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        self._log_start(input_path, output_path)
        result = _libreoffice_convert(input_path, output_path, "pdf")
        self._log_done(output_path)
        return result


# ---------------------------------------------------------------------------
# TXT → DOCX
# ---------------------------------------------------------------------------

class TxtToDocxConverter(BaseConverter):
    """Convert TXT → DOCX via LibreOffice headless."""

    source_format = "txt"
    target_format = "docx"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        self._log_start(input_path, output_path)
        result = _libreoffice_convert(input_path, output_path, "docx")
        self._log_done(output_path)
        return result


# ---------------------------------------------------------------------------
# TXT → MD  (trivial plain-text wrap)
# ---------------------------------------------------------------------------

class TxtToMarkdownConverter(BaseConverter):
    """Wrap a plain-text file in minimal Markdown (no-op essentially)."""

    source_format = "txt"
    target_format = "md"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        if not input_path.exists():
            raise FileMissingError(f"Source file not found: {input_path}")
        self._log_start(input_path, output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        text = input_path.read_text(encoding="utf-8", errors="replace")
        output_path.write_text(text, encoding="utf-8")
        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# MD → PDF  (via LibreOffice: md → txt → pdf intermediate)
# ---------------------------------------------------------------------------

class MdToPdfConverter(BaseConverter):
    """Convert Markdown → PDF via LibreOffice.

    Pipeline: .md content → write as .txt → LibreOffice → .pdf
    This avoids the heavy WeasyPrint + GTK/Cairo system dependency.
    """

    source_format = "md"
    target_format = "pdf"

    # Strip common Markdown syntax for cleaner LibreOffice rendering
    _STRIP_PATTERNS = [
        (re.compile(r"^#{1,6}\s+", re.MULTILINE), ""),
        (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
        (re.compile(r"\*(.+?)\*"), r"\1"),
        (re.compile(r"`{3}[\s\S]*?`{3}", re.MULTILINE), ""),
        (re.compile(r"`(.+?)`"), r"\1"),
        (re.compile(r"!\[.*?\]\(.*?\)"), ""),
        (re.compile(r"\[(.+?)\]\(.*?\)"), r"\1"),
        (re.compile(r"^[-*+]\s+", re.MULTILINE), ""),
        (re.compile(r"^\d+\.\s+", re.MULTILINE), ""),
        (re.compile(r"^>{1,}\s?", re.MULTILINE), ""),
        (re.compile(r"^-{3,}$", re.MULTILINE), ""),
    ]

    def convert(self, input_path: Path, output_path: Path) -> Path:
        if not input_path.exists():
            raise FileMissingError(f"Source file not found: {input_path}")
        self._log_start(input_path, output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="conv_md_pdf_") as tmp:
            tmp_dir = Path(tmp)
            # Write md content as a plain .txt so LibreOffice can render it
            raw = input_path.read_text(encoding="utf-8", errors="replace")
            for pattern, repl in self._STRIP_PATTERNS:
                raw = pattern.sub(repl, raw)
            txt_path = tmp_dir / (input_path.stem + ".txt")
            txt_path.write_text(raw, encoding="utf-8")
            pdf_tmp = _run_libreoffice(txt_path, "pdf", tmp_dir)
            shutil.move(str(pdf_tmp), str(output_path))

        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# MD → DOCX  (via LibreOffice: md → txt → docx)
# ---------------------------------------------------------------------------

class MdToDocxConverter(BaseConverter):
    """Convert Markdown → DOCX via LibreOffice."""

    source_format = "md"
    target_format = "docx"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        if not input_path.exists():
            raise FileMissingError(f"Source file not found: {input_path}")
        self._log_start(input_path, output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="conv_md_docx_") as tmp:
            tmp_dir = Path(tmp)
            raw = input_path.read_text(encoding="utf-8", errors="replace")
            txt_path = tmp_dir / (input_path.stem + ".txt")
            txt_path.write_text(raw, encoding="utf-8")
            docx_tmp = _run_libreoffice(txt_path, "docx", tmp_dir)
            shutil.move(str(docx_tmp), str(output_path))

        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Register all converters
# ---------------------------------------------------------------------------

registry.register(DocxToPdfConverter())
registry.register(DocxToTextConverter())
registry.register(DocxToMarkdownConverter())
registry.register(PdfToDocxConverter())
registry.register(TxtToPdfConverter())
registry.register(TxtToDocxConverter())
registry.register(TxtToMarkdownConverter())
registry.register(MdToPdfConverter())
registry.register(MdToDocxConverter())

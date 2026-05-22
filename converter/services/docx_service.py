"""
converter/services/docx_service.py

Converter for DOCX → PDF using LibreOffice headless.

LibreOffice is a **system dependency** — it must be installed separately
and available on PATH (or configured via settings.LIBREOFFICE_PATH).

Registered pair
---------------
- docx → pdf  (DocxToPdfConverter)
"""

from __future__ import annotations

import logging
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
# Defaults to "soffice" (on PATH).  On Windows it is often called "soffice.exe".
_LIBREOFFICE_BIN: str = getattr(settings, "LIBREOFFICE_PATH", "soffice")


class DocxToPdfConverter(BaseConverter):
    """Convert a DOCX file to PDF via LibreOffice headless.

    LibreOffice is invoked as a subprocess:
        soffice --headless --convert-to pdf <input.docx> --outdir <tmpdir>

    The resulting PDF is then moved to ``output_path``.
    Temporary files are always cleaned up.
    """

    source_format = "docx"
    target_format = "pdf"

    def convert(self, input_path: Path, output_path: Path) -> Path:
        """Run LibreOffice conversion and place result at ``output_path``.

        Args:
            input_path:  Path to the source .docx file.
            output_path: Desired path for the output .pdf file.

        Returns:
            Resolved ``output_path``.

        Raises:
            FileMissingError:      Source DOCX not found.
            ConversionFailedError: LibreOffice not found or conversion failed.
        """
        if not input_path.exists():
            raise FileMissingError(f"Source DOCX not found: {input_path}")
        self._log_start(input_path, output_path)
        self._ensure_parent(output_path)

        # Use a temporary directory so LibreOffice can write freely.
        with tempfile.TemporaryDirectory(prefix="conv_docx_") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            try:
                result = subprocess.run(
                    [
                        _LIBREOFFICE_BIN,
                        "--headless",
                        "--convert-to",
                        "pdf",
                        str(input_path),
                        "--outdir",
                        str(tmp_dir_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2-minute safety timeout
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

            # LibreOffice names the output file based on the input stem.
            expected_output = tmp_dir_path / (input_path.stem + ".pdf")
            if not expected_output.exists():
                raise ConversionFailedError(
                    f"LibreOffice did not produce the expected output "
                    f"'{expected_output.name}' in the temp directory."
                )

            shutil.move(str(expected_output), str(output_path))

        self._log_done(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

registry.register(DocxToPdfConverter())

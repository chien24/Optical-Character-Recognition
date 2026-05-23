"""
converter/services/conversion_manager.py

ConversionManager — the single entry point for all conversions.

Responsibilities
----------------
1. Import all service modules so their converters are registered.
2. Provide ``run()`` which orchestrates the full lifecycle:
   a. Resolve paths.
   b. Look up the converter in the registry.
   c. Execute the conversion.
   d. Persist the output file via the ``files`` app.
   e. Update the ``ConversionJob`` status.

Views and tasks MUST call ``ConversionManager.run()`` — never call a
converter directly from a view.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files import File

from .exceptions import ConversionError
from .registry import registry

# ---------------------------------------------------------------------------
# Force all service-module imports so they self-register their converters.
# ---------------------------------------------------------------------------
from . import docx_service  # noqa: F401  registers all LibreOffice-based converters
from . import pdf_service  # noqa: F401   registers pdf→txt, pdf→md

logger = logging.getLogger(__name__)

# Output directory relative to MEDIA_ROOT.
_OUTPUT_SUBDIR = "converter"


class ConversionManager:
    """Orchestrates a complete conversion job.

    This is a stateless utility class; all methods are static/class-level so
    no instantiation is needed::

        from converter.services.conversion_manager import ConversionManager
        ConversionManager.run(job)
    """

    @staticmethod
    def run(job) -> None:  # job: converter.models.ConversionJob
        """Execute a conversion job end-to-end.

        Args:
            job: A :class:`~converter.models.ConversionJob` instance in
                 PENDING or PROCESSING state.

        The job's status fields are updated in-place.  On success the
        ``output_file`` foreign key is populated.
        """
        from converter.models import ConversionJob  # local import avoids circular

        job.mark_processing()
        logger.info("ConversionManager: starting job id=%s", job.pk)

        input_path = Path(job.input_file.file.path)
        output_filename = ConversionManager._build_output_filename(
            job.input_file.original_name, job.target_format
        )
        output_dir = Path(settings.MEDIA_ROOT) / _OUTPUT_SUBDIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename

        try:
            converter = registry.get(job.source_format, job.target_format)
            actual_output = converter.convert(input_path, output_path)
        except ConversionError as exc:
            logger.error("ConversionManager: job id=%s failed: %s", job.pk, exc)
            job.mark_failed(str(exc))
            return
        except Exception as exc:
            logger.exception(
                "ConversionManager: unexpected error for job id=%s", job.pk
            )
            job.mark_failed(f"Unexpected error: {exc}")
            return

        # Persist output via the files app.
        output_file_record = ConversionManager._save_output_file(
            actual_output,
            original_name=output_filename,
            owner=job.input_file.owner,
        )
        job.mark_completed(output_file_record)
        logger.info("ConversionManager: job id=%s completed successfully", job.pk)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_output_filename(original_name: str, target_format: str) -> str:
        """Create a collision-free output filename."""
        stem = Path(original_name).stem
        unique = uuid.uuid4().hex[:8]
        return f"{stem}_{unique}.{target_format}"

    @staticmethod
    def _save_output_file(path: Path, original_name: str, owner=None):
        """Save the converted file to the files app and return the record."""
        from files.models import UploadedFile

        with path.open("rb") as fh:
            django_file = File(fh, name=path.name)
            record = UploadedFile.objects.create(
                owner=owner,
                original_name=original_name,
                file=django_file,
                size=path.stat().st_size,
                status="completed",
            )
        return record

    @staticmethod
    def supported_pairs() -> list[tuple[str, str]]:
        """Return all supported (source, target) pairs from the registry."""
        return registry.supported_pairs()

    @staticmethod
    def supported_targets_for(source_format: str) -> list[str]:
        """Return available target formats for a given source extension."""
        return registry.supported_targets_for(source_format)

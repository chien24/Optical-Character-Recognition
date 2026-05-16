import logging
from typing import Optional
from django.core.files.uploadedfile import UploadedFile as DjangoUploadedFile
from .models import UploadedFile

logger = logging.getLogger(__name__)


class FileService:
    """Service layer for file operations (validation, saving metadata)."""

    @staticmethod
    def save_uploaded_file(django_file: DjangoUploadedFile, owner=None) -> UploadedFile:
        """Persist uploaded file and return UploadedFile instance.

        This is a small synchronous helper; heavy file processing should be
        delegated to background tasks in `processing.services`.
        """

        uf = UploadedFile.objects.create(
            owner=owner,
            original_name=getattr(django_file, "name", "unknown"),
            file=django_file,
            mime_type=getattr(django_file, "content_type", ""),
            size=getattr(django_file, "size", None),
        )
        logger.debug("Saved UploadedFile id=%s", uf.id)
        return uf

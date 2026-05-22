"""
converter/models.py

Defines the ConversionJob model which tracks the lifecycle of each
file-conversion request. Output file is stored via the `files` app so
we never hardcode MEDIA_ROOT paths here.
"""

from django.db import models
from core.models import TimeStampedModel


class ConversionJob(TimeStampedModel):
    """Tracks a single file-conversion request end-to-end."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Nullable so we can construct the record before the output exists.
    input_file = models.ForeignKey(
        "files.UploadedFile",
        on_delete=models.CASCADE,
        related_name="conversion_jobs_as_input",
    )
    output_file = models.ForeignKey(
        "files.UploadedFile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversion_jobs_as_output",
    )

    source_format = models.CharField(max_length=16)
    target_format = models.CharField(max_length=16)

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Conversion Job"
        verbose_name_plural = "Conversion Jobs"

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"ConversionJob({self.source_format}→{self.target_format}, "
            f"{self.status}, id={self.pk})"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def mark_processing(self) -> None:
        self.status = self.Status.PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_completed(self, output_file) -> None:
        self.status = self.Status.COMPLETED
        self.output_file = output_file
        self.save(update_fields=["status", "output_file", "updated_at"])

    def mark_failed(self, error: str) -> None:
        self.status = self.Status.FAILED
        self.error_message = error
        self.save(update_fields=["status", "error_message", "updated_at"])

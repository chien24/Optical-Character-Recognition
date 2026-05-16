from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class UploadedFile(TimeStampedModel):
	STATUS_CHOICES = [
		("uploaded", "Uploaded"),
		("processing", "Processing"),
		("completed", "Completed"),
		("failed", "Failed"),
	]

	owner = models.ForeignKey(
		settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
	)
	original_name = models.CharField(max_length=1024)
	file = models.FileField(upload_to="uploads/%Y/%m/%d/")
	mime_type = models.CharField(max_length=255, blank=True)
	size = models.PositiveBigIntegerField(null=True, blank=True)
	status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="uploaded")
	metadata = models.JSONField(default=dict, blank=True)

	def __str__(self) -> str:  # pragma: no cover - simple
		return f"UploadedFile({self.original_name})"


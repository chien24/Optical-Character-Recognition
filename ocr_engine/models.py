from django.db import models
from core.models import TimeStampedModel
from processing.models import Job


class OCRResult(TimeStampedModel):
	job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name="ocr_result")
	text = models.TextField(blank=True)
	confidence = models.FloatField(null=True, blank=True)
	pages = models.PositiveIntegerField(null=True, blank=True)
	metadata = models.JSONField(default=dict, blank=True)

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"OCRResult(job={self.job_id})"


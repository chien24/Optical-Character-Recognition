from django.db import models
from django.conf import settings
from core.models import TimeStampedModel
from files.models import UploadedFile


class Job(TimeStampedModel):
	STATUS = [("pending", "Pending"), ("running", "Running"), ("success", "Success"), ("failed", "Failed")]

	JOB_TYPES = [
		("ocr", "OCR"),
		("pdf_merge", "PDF Merge"),
		("pdf_split", "PDF Split"),
		("translate", "Translate"),
	]

	job_type = models.CharField(max_length=64, choices=JOB_TYPES)
	status = models.CharField(max_length=32, choices=STATUS, default="pending")
	input_file = models.ForeignKey(UploadedFile, null=True, blank=True, on_delete=models.SET_NULL, related_name="jobs")
	result_file = models.ForeignKey(UploadedFile, null=True, blank=True, on_delete=models.SET_NULL, related_name="job_results")
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
	params = models.JSONField(default=dict, blank=True)
	logs = models.TextField(blank=True)
	started_at = models.DateTimeField(null=True, blank=True)
	finished_at = models.DateTimeField(null=True, blank=True)

	def __str__(self) -> str:  # pragma: no cover - trivial
		return f"Job({self.job_type} id={self.id})"


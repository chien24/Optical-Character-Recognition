from django.db import models


class TimeStampedModel(models.Model):
	"""Abstract base model that provides created/updated timestamps."""

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class UUIDModel(TimeStampedModel):
	"""Base model that can be extended for common id/metadata in future.

	Keep simple so other apps can inherit for consistent timestamps.
	"""

	class Meta:
		abstract = True


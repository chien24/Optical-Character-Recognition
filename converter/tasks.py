"""
converter/tasks.py

Celery task wrappers for async conversion.

These tasks delegate entirely to ConversionManager.run().
Celery is already listed in requirements.txt (celery==5.3.1 + redis==4.5.1).

To enable async conversion:
1. Configure CELERY_BROKER_URL in settings (e.g. redis://localhost:6379/0).
2. Replace the synchronous ``ConversionManager.run(job)`` call in views.py
   with ``run_conversion_task.delay(job.pk)``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task  # type: ignore

    @shared_task(
        bind=True,
        autoretry_for=(Exception,),
        retry_kwargs={"max_retries": 2, "countdown": 5},
        name="converter.tasks.run_conversion_task",
    )
    def run_conversion_task(self, job_pk: int) -> dict:
        """Celery task: run a ConversionJob by primary key.

        Args:
            job_pk: Primary key of the :class:`~converter.models.ConversionJob`.

        Returns:
            A dict with ``{"status": ..., "job_pk": ...}`` for result back-ends.
        """
        from converter.models import ConversionJob
        from converter.services import ConversionManager

        try:
            job = ConversionJob.objects.get(pk=job_pk)
        except ConversionJob.DoesNotExist:
            logger.error("run_conversion_task: job pk=%s not found", job_pk)
            return {"status": "not_found", "job_pk": job_pk}

        ConversionManager.run(job)
        job.refresh_from_db()
        logger.info(
            "run_conversion_task: job pk=%s finished with status=%s",
            job_pk,
            job.status,
        )
        return {"status": job.status, "job_pk": job_pk}

except ImportError:
    # Celery not installed (unlikely given requirements.txt, but safe to guard).
    logger.warning(
        "Celery is not installed; async conversion tasks are unavailable. "
        "Install celery and configure a broker to enable them."
    )

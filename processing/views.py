"""
processing/views.py

Views for the processing app.

Endpoints
---------
GET  /processing/status/<pk>/  → job_status  : display job details and result
POST /processing/delete/<pk>/  → delete_job  : delete a job and redirect to history
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Job

logger = logging.getLogger(__name__)


@require_GET
def job_status(request, pk: int):
    """Display the status and result of any processing job."""
    job = get_object_or_404(Job, pk=pk)

    # Attach OCR result if available
    ocr_result = None
    if job.job_type == "ocr":
        ocr_result = getattr(job, "ocr_result", None)

    ctx = {
        "active_page": "history",
        "job": job,
        "ocr_result": ocr_result,
    }
    return render(request, "processing/job_status.html", ctx)


@require_POST
def delete_job(request, pk: int):
    """Delete a processing job record and redirect to history."""
    job = get_object_or_404(Job, pk=pk)
    job_id = job.pk
    try:
        job.delete()
        messages.success(request, f"Job #{job_id} deleted successfully.")
    except Exception:
        logger.exception("Failed to delete job id=%s", job_id)
        messages.error(request, f"Failed to delete job #{job_id}.")
    return redirect("core:history")

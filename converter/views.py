"""
converter/views.py

Views for the converter app.  Views contain ZERO business logic — they
only validate forms, call ConversionManager, and return responses.

Endpoints
---------
- GET/POST  /convert/          → convert()  (upload + trigger conversion)
- GET        /convert/<int:pk>/ → conversion_detail()  (status + download)
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from files.services import FileService
from .forms import ConversionForm
from .models import ConversionJob
from .services import ConversionManager

logger = logging.getLogger(__name__)

# Popular conversion chips shown on the page (for UI affordance).
_POPULAR_CONVERSIONS = [
    {"from_fmt": "docx", "to_fmt": "pdf",  "label": "DOCX → PDF"},
    {"from_fmt": "pdf",  "to_fmt": "txt",  "label": "PDF → Text"},
    {"from_fmt": "pdf",  "to_fmt": "md",   "label": "PDF → Markdown"},
    {"from_fmt": "png",  "to_fmt": "pdf",  "label": "Image → PDF"},
    {"from_fmt": "md",   "to_fmt": "pdf",  "label": "Markdown → PDF"},
    {"from_fmt": "md",   "to_fmt": "txt",  "label": "Markdown → Text"},
]


@require_http_methods(["GET", "POST"])
def convert(request: HttpRequest) -> HttpResponse:
    """Main converter page.

    GET:  Render the upload form.
    POST: Validate form → save uploaded file → create ConversionJob →
          run conversion → redirect to detail page.
    """
    form = ConversionForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            django_file = form.cleaned_data["file"]
            target_format = form.cleaned_data["target_format"]
            src_ext = django_file.name.rsplit(".", 1)[-1].lower()
            owner = request.user if request.user.is_authenticated else None

            # 1. Persist the uploaded file via the files app.
            uploaded_file = FileService.save_uploaded_file(django_file, owner=owner)

            # 2. Create the conversion job record.
            job = ConversionJob.objects.create(
                input_file=uploaded_file,
                source_format=src_ext,
                target_format=target_format,
            )

            # 3. Run conversion synchronously (tasks.py wraps this for Celery).
            ConversionManager.run(job)
            job.refresh_from_db()

            if job.status == ConversionJob.Status.COMPLETED:
                messages.success(request, "Conversion completed successfully!")
            else:
                messages.error(request, f"Conversion failed: {job.error_message}")

            return redirect("converter:conversion_detail", pk=job.pk)
        else:
            messages.error(request, "Please correct the errors below.")

    ctx = {
        "active_page": "converter",
        "form": form,
        "popular_conversions": _POPULAR_CONVERSIONS,
        "supported_pairs": ConversionManager.supported_pairs(),
    }
    return render(request, "converter/index.html", ctx)


@require_http_methods(["GET"])
def conversion_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show the status and download link for a conversion job."""
    job = get_object_or_404(ConversionJob, pk=pk)
    ctx = {
        "active_page": "converter",
        "job": job,
    }
    return render(request, "converter/detail.html", ctx)

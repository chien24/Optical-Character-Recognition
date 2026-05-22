"""
ocr_engine/views.py

Views for the OCR engine app. Follows the service-layer architecture:
- Views do NOT contain business logic.
- All OCR execution is delegated to OCREngineService / run_ocr_pipeline.

Endpoints
---------
GET  /         (dashboard – handled in core, but OCR form posts here)
POST /ocr/run/ → start_ocr    : accept upload + settings → run OCR → redirect to result
GET  /ocr/<pk>/ → view_result : display OCRResult for a given Job pk
POST /ocr/api/upload/ → upload_and_run_ocr : JSON API endpoint (existing, preserved)
"""
from __future__ import annotations

import logging
import uuid

from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from files.services import FileService
from processing.models import Job
from processing.services import ProcessingService
from .models import OCRResult
from .services.ocr_pipeline import run_ocr_pipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML Form endpoint: POST /ocr/run/
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
def start_ocr(request):
    """Accept image/PDF upload from dashboard form, run custom PyTorch OCR, save result.

    Form fields (multipart/form-data):
        file          – uploaded image or PDF
        export_md     – checkbox: export Markdown output
        export_txt    – checkbox: export plain-text output
        ocr_model     – ignored (only custom model is used)
        ocr_language  – stored in job params for future use
    """
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        messages.error(request, "No file uploaded. Please select an image or PDF file.")
        return redirect("core:dashboard")

    owner = request.user if request.user.is_authenticated else None

    # ── 1. Persist the uploaded file ──────────────────────────────────────
    try:
        saved_file = FileService.save_uploaded_file(uploaded_file, owner=owner)
    except Exception:
        logger.exception("Failed to save uploaded file")
        messages.error(request, "Failed to save the uploaded file. Please try again.")
        return redirect("core:dashboard")

    # ── 2. Create a Job record ────────────────────────────────────────────
    export_md = bool(request.POST.get("export_md"))
    export_txt = bool(request.POST.get("export_txt"))
    ocr_language = request.POST.get("ocr_language", "Auto-detect")

    job = ProcessingService.create_job(
        "ocr",
        input_file=saved_file,
        created_by=owner,
        params={
            "ocr_model": "Custom PyTorch (ResNetEncoder)",
            "ocr_language": ocr_language,
            "export_md": export_md,
            "export_txt": export_txt,
        },
    )

    # ── 3. Run OCR via service layer ──────────────────────────────────────
    job.status = "running"
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        image_path = saved_file.file.path
        result = run_ocr_pipeline(image_path)
        ocr_text = result.get("corrected_text") or result.get("raw_text", "")

        # ── 4. Persist OCRResult ──────────────────────────────────────────
        OCRResult.objects.create(
            job=job,
            text=ocr_text,
            confidence=None,  # custom model doesn't expose per-token confidence
            pages=1,
            metadata={
                "raw_text": result.get("raw_text", ""),
                "ocr_time": result.get("ocr_time"),
                "correction_time": result.get("correction_time"),
                "total_time": result.get("total_time"),
                "engine": "CustomPytorchEngine (ResNetEncoder)",
            },
        )

        # ── 5. Save result files ──────────────────────────────────────────
        # Always save Markdown output by default; also txt if requested.
        base_name = saved_file.original_name.rsplit(".", 1)[0]
        result_file = None

        if export_md or not export_txt:
            md_content = _format_as_markdown(ocr_text, saved_file.original_name)
            md_name = f"ocr_results/{uuid.uuid4().hex}_{base_name}.md"
            saved_md = default_storage.save(md_name, ContentFile(md_content.encode("utf-8")))
            result_file = _make_uploaded_file(saved_md, f"{base_name}.md", "text/markdown", owner)

        elif export_txt:
            txt_name = f"ocr_results/{uuid.uuid4().hex}_{base_name}.txt"
            saved_txt = default_storage.save(txt_name, ContentFile(ocr_text.encode("utf-8")))
            result_file = _make_uploaded_file(saved_txt, f"{base_name}.txt", "text/plain", owner)

        # ── 6. Update job to completed ────────────────────────────────────
        job.status = "success"
        job.finished_at = timezone.now()
        job.result_file = result_file
        job.save(update_fields=["status", "finished_at", "result_file"])

        messages.success(request, "OCR completed successfully!")
        return redirect("ocr_engine:view_result", pk=job.pk)

    except Exception as exc:
        logger.exception("OCR pipeline failed for job id=%s", job.pk)
        job.status = "failed"
        job.finished_at = timezone.now()
        job.logs = str(exc)
        job.save(update_fields=["status", "finished_at", "logs"])
        messages.error(request, f"OCR failed: {exc}")
        return redirect("core:dashboard")


# ---------------------------------------------------------------------------
# Result view: GET /ocr/<pk>/
# ---------------------------------------------------------------------------

@require_GET
def view_result(request, pk: int):
    """Display the OCR result for a completed job."""
    job = get_object_or_404(Job, pk=pk, job_type="ocr")
    ocr_result = getattr(job, "ocr_result", None)

    ctx = {
        "active_page": "ocr",
        "job": job,
        "ocr_result": ocr_result,
    }
    return render(request, "ocr_engine/result.html", ctx)


# ---------------------------------------------------------------------------
# JSON API endpoint (existing, preserved): POST /ocr/api/upload/
# ---------------------------------------------------------------------------

@require_POST
def upload_and_run_ocr(request):
    """Accept a single uploaded image file and run OCR pipeline.

    Returns JSON with: raw_text, corrected_text, ocr_time, correction_time, total_time
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "no file uploaded"}, status=400)

    tmp_name = f"ocr_upload_{uuid.uuid4().hex}_{uploaded.name}"
    saved_name = default_storage.save(tmp_name, ContentFile(uploaded.read()))
    try:
        abs_path = default_storage.path(saved_name)
        result = run_ocr_pipeline(abs_path)
        return JsonResponse(result)
    except Exception:
        logger.exception("Error running OCR on uploaded file")
        return JsonResponse({"error": "internal error"}, status=500)
    finally:
        try:
            default_storage.delete(saved_name)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_as_markdown(text: str, original_filename: str) -> str:
    """Wrap plain OCR text in a basic Markdown document."""
    return (
        f"# OCR Result: {original_filename}\n\n"
        f"---\n\n"
        f"{text}\n"
    )


def _make_uploaded_file(storage_name: str, original_name: str, mime_type: str, owner):
    """Create an UploadedFile record for a file already saved via default_storage."""
    from files.models import UploadedFile
    import os
    try:
        size = default_storage.size(storage_name)
    except Exception:
        size = None
    return UploadedFile.objects.create(
        owner=owner,
        original_name=original_name,
        file=storage_name,
        mime_type=mime_type,
        size=size,
    )

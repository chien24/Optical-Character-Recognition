from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def dashboard(request):
    """Render the OCR processing / home page."""
    ctx = {"active_page": "ocr"}
    # recent_files will be populated when files app is wired up
    if request.user.is_authenticated:
        try:
            from files.models import UploadedFile
            ctx["recent_files"] = UploadedFile.objects.filter(
                owner=request.user
            ).order_by("-uploaded_at")[:5]
        except Exception:
            ctx["recent_files"] = []
    return render(request, "core/dashboard.html", ctx)


def history(request):
    """Processing history page."""
    ctx = {"active_page": "history", "jobs": [], "stats": {}}
    if request.user.is_authenticated:
        try:
            from processing.models import Job
            jobs = Job.objects.filter(created_by=request.user).order_by("-created_at")
            ctx["jobs"] = jobs
            ctx["stats"] = {
                "total": jobs.count(),
                "completed": jobs.filter(status="completed").count(),
                "processing": jobs.filter(status="processing").count(),
                "failed": jobs.filter(status="failed").count(),
            }
        except Exception:
            pass
    return render(request, "core/history.html", ctx)


def settings(request):
    """Settings page."""
    return render(request, "core/settings.html", {"active_page": "settings"})


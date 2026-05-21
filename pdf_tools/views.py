"""
pdf_tools/views.py

View handlers for all 10 PDF tools.

Design decisions:
- Each tool has a dedicated POST handler; GET handlers render the UI page.
- Heavy work is delegated to service layer (pdf_tools.services.*).
- All views return JSON responses for API compatibility and
  Django template rendering for web UI.
- No business logic lives in views.
"""

from __future__ import annotations

import json
import logging
import os

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from pdf_tools import services
from pdf_tools.exceptions import PDFToolsError
from pdf_tools.services.utils import PDF_OUTPUT_DIR

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "error": message}, status=status)


def _success_response(data: dict) -> JsonResponse:
    return JsonResponse({"success": True, **data})


def _get_uploaded_file_path(request) -> str | None:
    """Extract a file path from POST data or an uploaded file."""
    if request.FILES.get("file"):
        f = request.FILES["file"]
        # Save temp file to output dir
        tmp_path = os.path.join(PDF_OUTPUT_DIR, "uploads", f.name)
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "wb+") as dest:
            for chunk in f.chunks():
                dest.write(chunk)
        return tmp_path
    return request.POST.get("file_path") or None


# ---------------------------------------------------------------------------
# Index / landing
# ---------------------------------------------------------------------------

def index(request):
    """PDF Tools landing page with tool grid."""
    return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools"})


# ---------------------------------------------------------------------------
# 1. Merge PDF
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def merge(request):
    """Merge multiple PDFs into one.

    POST params:
        file_path[] — list of absolute/media paths to source PDFs
            OR
        file[]      — multiple uploaded PDF files
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "merge"})

    # Collect file paths from POST
    file_paths = request.POST.getlist("file_path[]")

    # Handle uploaded files
    uploaded_files = request.FILES.getlist("file[]")
    upload_dir = os.path.join(PDF_OUTPUT_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    for f in uploaded_files:
        tmp_path = os.path.join(upload_dir, f.name)
        with open(tmp_path, "wb+") as dest:
            for chunk in f.chunks():
                dest.write(chunk)
        file_paths.append(tmp_path)

    if len(file_paths) < 2:
        return _error_response("At least 2 PDF files are required for merge.")

    try:
        output_path = services.merge_pdfs(file_paths)
        return _success_response({"output_path": output_path, "file_count": len(file_paths)})
    except PDFToolsError as exc:
        logger.warning("Merge failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in merge view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 2. Split PDF
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def split(request):
    """Split a PDF by page ranges.

    POST params:
        file_path   — path to source PDF
        ranges      — range string e.g. "1-3,5,7-9" (omit for split-all)
        split_all   — "true" to split into individual pages
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "split"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    split_all = request.POST.get("split_all", "false").lower() == "true"
    ranges_str = request.POST.get("ranges", "").strip()

    try:
        if split_all or not ranges_str:
            output_paths = services.split_all_pages(file_path)
        else:
            output_paths = services.split_pdf_by_ranges_str(file_path, ranges_str)

        return _success_response({"output_paths": output_paths, "parts": len(output_paths)})
    except PDFToolsError as exc:
        logger.warning("Split failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in split view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 3. Extract from PDF
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def extract(request):
    """Extract text, images, or metadata from a PDF.

    POST params:
        file_path       — path to source PDF
        extract_type    — "text" | "images" | "metadata"
        page_nums       — comma-separated 1-indexed pages (optional)
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "extract"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    extract_type = request.POST.get("extract_type", "text")
    page_nums_raw = request.POST.get("page_nums", "").strip()
    page_nums = None
    if page_nums_raw:
        try:
            page_nums = [int(p.strip()) for p in page_nums_raw.split(",") if p.strip()]
        except ValueError:
            return _error_response("page_nums must be comma-separated integers.")

    try:
        if extract_type == "metadata":
            result = services.extract_metadata(file_path)
            return _success_response({"metadata": result})
        elif extract_type == "images":
            paths = services.extract_images(file_path, page_nums=page_nums)
            return _success_response({"image_paths": paths, "count": len(paths)})
        else:  # default: text
            result = services.extract_text(file_path, page_nums=page_nums)
            return _success_response({
                "full_text": result.get("full_text", ""),
                "pages": result.get("pages", []),
                "page_count": result.get("page_count"),
            })
    except PDFToolsError as exc:
        logger.warning("Extract failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in extract view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 4. Reorder pages
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def reorder(request):
    """Reorder PDF pages.

    POST params:
        file_path  — source PDF path
        order      — JSON array of 0-indexed page indices, e.g. "[2,0,1]"
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "reorder"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    order_raw = request.POST.get("order", "")
    try:
        order = json.loads(order_raw)
        if not isinstance(order, list):
            raise ValueError("order must be a JSON array.")
        order = [int(i) for i in order]
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return _error_response(f"Invalid order parameter: {exc}")

    try:
        output_path = services.reorder_pages(file_path, order)
        return _success_response({"output_path": output_path, "order": order})
    except PDFToolsError as exc:
        logger.warning("Reorder failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in reorder view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 5. Delete pages
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def delete_pages_view(request):
    """Delete selected pages from a PDF.

    POST params:
        file_path  — source PDF path
        pages      — comma-separated 1-indexed page numbers, e.g. "2,4,6"
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "delete_pages"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    pages_raw = request.POST.get("pages", "").strip()
    try:
        pages = [int(p.strip()) for p in pages_raw.split(",") if p.strip()]
    except ValueError:
        return _error_response("pages must be comma-separated integers.")

    if not pages:
        return _error_response("At least one page number is required.")

    try:
        output_path = services.delete_pages(file_path, pages)
        return _success_response({"output_path": output_path, "deleted_pages": pages})
    except PDFToolsError as exc:
        logger.warning("Delete pages failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in delete_pages view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 6. Rotate pages
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def rotate(request):
    """Rotate selected (or all) pages in a PDF.

    POST params:
        file_path  — source PDF path
        pages      — comma-separated 1-indexed page numbers (empty = all pages)
        angle      — 90 | 180 | 270
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "rotate"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    pages_raw = request.POST.get("pages", "").strip()
    try:
        pages = [int(p.strip()) for p in pages_raw.split(",") if p.strip()]
    except ValueError:
        return _error_response("pages must be comma-separated integers.")

    try:
        angle = int(request.POST.get("angle", 90))
    except ValueError:
        return _error_response("angle must be an integer (90, 180, or 270).")

    try:
        output_path = services.rotate_pages(file_path, pages, angle)
        return _success_response({
            "output_path": output_path,
            "rotated_pages": pages or "all",
            "angle": angle,
        })
    except PDFToolsError as exc:
        logger.warning("Rotate failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in rotate view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 7. Compress PDF
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def compress(request):
    """Compress a PDF file.

    POST params:
        file_path       — source PDF path
        image_quality   — integer 1-100 (default 80)
        linearize       — "true" | "false"
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "compress"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    try:
        image_quality = int(request.POST.get("image_quality", 80))
    except ValueError:
        return _error_response("image_quality must be an integer between 1 and 100.")

    linearize = request.POST.get("linearize", "false").lower() == "true"

    try:
        original_size = os.path.getsize(file_path) if os.path.isfile(file_path) else None
        output_path = services.compress_pdf(file_path, image_quality=image_quality, linearize=linearize)
        compressed_size = os.path.getsize(output_path) if os.path.isfile(output_path) else None

        return _success_response({
            "output_path": output_path,
            "original_size_bytes": original_size,
            "compressed_size_bytes": compressed_size,
        })
    except PDFToolsError as exc:
        logger.warning("Compress failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in compress view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 8. Watermark PDF
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def watermark(request):
    """Add a text or image watermark to a PDF.

    POST params (text watermark):
        file_path       — source PDF path
        watermark_type  — "text" | "image"
        text            — watermark text (for type=text)
        watermark_image — uploaded image file (for type=image)
        opacity         — float 0.0-1.0 (default 0.3)
        position        — "center" | "top-left" | etc.
        pages           — comma-separated 1-indexed pages (empty = all)
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "watermark"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    watermark_type = request.POST.get("watermark_type", "text")
    position = request.POST.get("position", "center")
    pages_raw = request.POST.get("pages", "").strip()

    try:
        opacity = float(request.POST.get("opacity", 0.3))
    except ValueError:
        return _error_response("opacity must be a float between 0.0 and 1.0.")

    try:
        pages = [int(p.strip()) for p in pages_raw.split(",") if p.strip()]
    except ValueError:
        return _error_response("pages must be comma-separated integers.")

    try:
        if watermark_type == "image":
            wm_file = request.FILES.get("watermark_image")
            if not wm_file:
                return _error_response("watermark_image file is required for image watermark.")
            wm_path = os.path.join(PDF_OUTPUT_DIR, "uploads", wm_file.name)
            os.makedirs(os.path.dirname(wm_path), exist_ok=True)
            with open(wm_path, "wb+") as dest:
                for chunk in wm_file.chunks():
                    dest.write(chunk)
            output_path = services.add_image_watermark(
                file_path, wm_path, opacity=opacity, position=position,
                pages=pages or None,
            )
        else:
            text = request.POST.get("text", "").strip()
            if not text:
                return _error_response("text is required for text watermark.")
            output_path = services.add_text_watermark(
                file_path, text, opacity=opacity, position=position,
                pages=pages or None,
            )

        return _success_response({"output_path": output_path, "watermark_type": watermark_type})
    except PDFToolsError as exc:
        logger.warning("Watermark failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in watermark view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 9. Encrypt PDF
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def encrypt(request):
    """Encrypt a PDF with a password.

    POST params:
        file_path       — source PDF path
        user_password   — password to open the document
        owner_password  — full-control password (defaults to user_password)
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "encrypt"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    user_pw = request.POST.get("user_password", "").strip()
    if not user_pw:
        return _error_response("user_password is required.")

    owner_pw = request.POST.get("owner_password", user_pw).strip() or user_pw

    try:
        output_path = services.encrypt_pdf(file_path, user_pw, owner_pw)
        return _success_response({"output_path": output_path})
    except PDFToolsError as exc:
        logger.warning("Encrypt failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in encrypt view")
        return _error_response(f"Unexpected error: {exc}", status=500)


# ---------------------------------------------------------------------------
# 10. Generate Preview / Thumbnail
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def preview(request):
    """Generate a preview image from a PDF page.

    POST params:
        file_path   — source PDF path
        page_num    — 1-indexed page number (default 1)
        dpi         — resolution (default 150)
        all_pages   — "true" to render all pages
    """
    if request.method == "GET":
        return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools", "tool": "preview"})

    file_path = _get_uploaded_file_path(request)
    if not file_path:
        return _error_response("file_path or file upload is required.")

    all_pages = request.POST.get("all_pages", "false").lower() == "true"

    try:
        dpi = int(request.POST.get("dpi", 150))
        page_num = int(request.POST.get("page_num", 1))
    except ValueError:
        return _error_response("dpi and page_num must be integers.")

    try:
        if all_pages:
            paths = services.generate_all_previews(file_path, dpi=dpi)
            return _success_response({"preview_paths": paths, "count": len(paths)})
        else:
            output_path = services.generate_preview(file_path, page_num=page_num, dpi=dpi)
            return _success_response({"preview_path": output_path, "page_num": page_num})
    except PDFToolsError as exc:
        logger.warning("Preview failed: %s", exc)
        return _error_response(str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in preview view")
        return _error_response(f"Unexpected error: {exc}", status=500)

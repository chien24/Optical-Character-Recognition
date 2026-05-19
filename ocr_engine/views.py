import uuid
import logging

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .services.ocr_pipeline import run_ocr_pipeline

logger = logging.getLogger(__name__)


@require_POST
def upload_and_run_ocr(request):
	"""Accept a single uploaded image file and run OCR pipeline.

	Uses the service layer (`ocr_pipeline`) for business logic. Returns JSON.
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

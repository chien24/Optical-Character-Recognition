import logging
from .models import OCRResult
from processing.models import Job

logger = logging.getLogger(__name__)


class OCREngineService:
    """High-level orchestration for OCR engines.

    Chooses a concrete engine implementation and runs OCR. Engines live
    under `ocr_engine.services.engines` and should follow `BaseEngine`.
    """

    @staticmethod
    def run_ocr(job: Job) -> OCRResult:
        engine_name = job.params.get("ocr_model", "custom") if job.params else "custom"
        try:
            from .services.engines.factory import get_engine
            engine = get_engine(engine_name)
        except Exception:
            logger.exception("Failed to load OCR engine %s", engine_name)
            engine = None

        if engine is not None and hasattr(engine, "run"):
            image_path = getattr(job.input_file.file, "path", "")
            result = engine.run(image_path, options=job.params)
            ocr_text = result.get("text", "")
            confidence = result.get("confidence")
            pages = result.get("pages")
            metadata = result.get("metadata", {})
        else:
            ocr_text = ""
            confidence = None
            pages = 0
            metadata = {}

        orr = OCRResult.objects.create(
            job=job, text=ocr_text, confidence=confidence, pages=pages, metadata=metadata
        )
        logger.info("Created OCRResult for job=%s using %s engine", job.id, engine_name)
        return orr

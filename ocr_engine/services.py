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
        engine_name = job.params.get("engine", "tesseract") if job.params else "tesseract"

        # lazy import of engines to avoid heavy deps at module import time
        if engine_name == "tesseract":
            try:
                from .services.engines.tesseract_service import TesseractEngine

                engine = TesseractEngine()
            except Exception:
                logger.exception("Failed to load TesseractEngine; falling back to placeholder")
                engine = None
        else:
            engine = None

        # Execute engine if available (placeholder behavior otherwise)
        if engine is not None and hasattr(engine, "run"):
            # Real implementations should accept file paths, pages, options
            result = engine.run(getattr(job.input_file.file, "path", ""), options=job.params)
            ocr_text = result.get("text", "")
            confidence = result.get("confidence")
            pages = result.get("pages")
        else:
            ocr_text = ""
            confidence = None
            pages = 0

        orr = OCRResult.objects.create(job=job, text=ocr_text, confidence=confidence, pages=pages, metadata={})
        logger.info("Created OCRResult for job=%s engine=%s", job.id, engine_name)
        return orr

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
        # This project uses a single custom PyTorch OCR model (ResNetEncoder).
        # Always use the CustomPytorchEngine; do not support multiple engines.
        try:
            from .services.engines.custom_pytorch_service import CustomPytorchEngine

            engine = CustomPytorchEngine()
        except Exception:
            logger.exception("Failed to load CustomPytorchEngine; ensure model and dependencies are available")
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

        orr = OCRResult.objects.create(
            job=job, text=ocr_text, confidence=confidence, pages=pages, metadata=metadata if "metadata" in locals() else {}
        )
        logger.info("Created OCRResult for job=%s using CustomPytorchEngine", job.id)
        return orr

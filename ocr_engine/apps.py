from django.apps import AppConfig


class OcrEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ocr_engine'

    def ready(self):
        # Attempt to initialize the OCR model once when the app is ready.
        # If the model file is not present, skip initialization and log at info level.
        try:
            # Lazy import to avoid importing heavy ML libs at module import time
            import logging
            from pathlib import Path

            from .services import model_loader

            paths = model_loader._resolve_paths()
            model_path = paths.get("model_path")

            if model_path and Path(model_path).exists():
                model_loader.initialize_model()
            else:
                logging.getLogger(__name__).info(
                    "OCR model not found at %s; skipping initialization on startup.", model_path
                )
        except Exception:
            # Do not crash the whole Django process if model loading fails; log instead.
            import logging

            logging.getLogger(__name__).exception("Failed to initialize OCR model on app ready.")

"""Service package for ocr_engine.

This package exposes the recommended public API at the top level:

    from ocr_engine.services.document_ocr_service import run_document_ocr
    from ocr_engine.services.ocr_pipeline import run_ocr_on_pil_image
    from ocr_engine.services.preprocess_service import load_image, ImagePreprocessor

Submodule hierarchy:
    model_loader         — singleton model cache (loaded on Django startup via apps.py:ready())
    preprocess_service   — load_image() + ImagePreprocessor.preprocess_pil()
    inference_service    — extract_text_from_pil()
    decode_service       — greedy_decode() + indices_to_string()
    ocr_pipeline         — run_ocr_on_pil_image() [single image, full pipeline]
    correction_service   — correct_with_ollama() [optional LLM post-processing]
    document_ocr_service — run_document_ocr()   [top-level: image + PDF support]
    engines/             — BaseEngine + CustomPytorchEngine adapter

Note: model_loader (and torch) is NOT imported here at package level to avoid
circular imports and to prevent torch from loading before apps.py:ready() runs.
The model is loaded lazily on first inference call via get_model().
"""
# Intentionally empty — submodules are imported on demand.

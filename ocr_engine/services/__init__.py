"""Service package for ocr_engine.

This package marker ensures imports like `ocr_engine.services.model_loader`
resolve to the subpackage rather than a top-level module.
"""

from . import model_loader  # expose common submodules for convenience

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseEngine(ABC):
    """Abstract OCR engine interface."""

    @abstractmethod
    def run(self, image_path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run OCR on image_path and return result dict with keys: text, confidence, pages."""

        raise NotImplementedError()

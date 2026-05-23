"""ocr_engine/services/preprocess_service.py

Image preprocessing for the custom PyTorch OCR model (ResNetEncoder).

Boundary:
    This module accepts PIL.Image or numpy.ndarray objects only.
    It does NOT access the filesystem.

    To load an image from disk, use the module-level helper:
        pil_img = load_image(path)
    Then preprocess via:
        tensor, valid_w = preprocessor.preprocess_pil(pil_img)
"""
from __future__ import annotations

import logging
import warnings
from typing import List, Tuple, Union

import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms

from ..torch_models.ocr_model import IMG_HEIGHT, IMG_WIDTH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filesystem loader — separated from preprocessing logic
# ---------------------------------------------------------------------------

def load_image(path: str) -> Image.Image:
    """Load an image from *path* and return it as a PIL.Image in RGB mode.

    This is the ONLY function in the OCR service layer that should touch the
    filesystem.  All downstream preprocessing functions accept PIL.Image
    objects so that they remain decoupled from storage concerns.

    Args:
        path: Absolute path to the image file (PNG, JPG, JPEG, WEBP, etc.).

    Returns:
        PIL.Image in RGB mode.

    Raises:
        PIL.UnidentifiedImageError: if Pillow cannot identify the file format.
        FileNotFoundError:          if the path does not exist.
    """
    return Image.open(path).convert("RGB")


# ---------------------------------------------------------------------------
# Preprocessor class
# ---------------------------------------------------------------------------

class ImagePreprocessor:
    """Preprocess images into model-ready tensors for the OCR model.

    Primary entry point: :meth:`preprocess_pil` — accepts a PIL.Image.
    Filesystem path support is available via the deprecated :meth:`preprocess`
    for backward compatibility only.
    """

    def __init__(
        self,
        target_height: int = IMG_HEIGHT,
        max_width: int = IMG_WIDTH,
        enhance_contrast: bool = False,
        denoise: bool = False,
        binarize: bool = False,
    ):
        self.target_height = target_height
        self.max_width = max_width
        self.enhance_contrast = enhance_contrast
        self.denoise = denoise
        self.binarize = binarize

        self.transform = transforms.Compose([
            transforms.Grayscale(1),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5]),
        ])

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _enhance(self, pil_img: Image.Image) -> Image.Image:
        """Apply optional image enhancement operations (CLAHE, denoise, binarize)."""
        img_np = np.array(pil_img.convert("L"))

        if self.denoise:
            img_np = cv2.medianBlur(img_np, 3)

        if self.enhance_contrast:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_np = clahe.apply(img_np)

        if self.binarize:
            _, img_np = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return Image.fromarray(img_np).convert("RGB")

    # -----------------------------------------------------------------------
    # Primary API — accepts PIL.Image (no filesystem access)
    # -----------------------------------------------------------------------

    def preprocess_pil(self, pil_img: Image.Image) -> Tuple[torch.Tensor, int]:
        """Preprocess a PIL.Image into a model-ready tensor.

        This is the **primary** preprocessing method. It does not access the
        filesystem. Callers are responsible for loading the image first, e.g.
        via :func:`load_image` or by rendering a PDF page with
        ``pdf_render_service.render_page_to_pil``.

        Args:
            pil_img: A PIL.Image in any mode; converted to RGB internally.

        Returns:
            Tuple of (tensor, valid_width) where:
                tensor      — shape (1, 1, H, W), float32, normalised [-1, 1]
                valid_width — actual content width before padding (int)
        """
        img = pil_img.convert("RGB")

        if self.denoise or self.enhance_contrast or self.binarize:
            img = self._enhance(img)

        tensor = self.transform(img)

        c, h, w = tensor.shape
        new_w = max(1, int(w * self.target_height / h))
        new_w = min(new_w, self.max_width)

        tensor_resized = F.interpolate(
            tensor.unsqueeze(0),
            size=(self.target_height, new_w),
            mode="bilinear",
            align_corners=False,
        ).squeeze(0)

        padded = torch.full((c, self.target_height, self.max_width), 1.0, dtype=tensor.dtype)
        padded[:, :, :new_w] = tensor_resized

        return padded.unsqueeze(0), new_w

    # -----------------------------------------------------------------------
    # Deprecated path-based API — kept for backward compatibility
    # -----------------------------------------------------------------------

    def preprocess(self, image_path: str) -> Tuple[torch.Tensor, int]:
        """[DEPRECATED] Preprocess an image from a filesystem path.

        .. deprecated::
            Use :func:`load_image` + :meth:`preprocess_pil` instead.
            Path-based preprocessing couples filesystem concerns into the
            preprocessing layer, making it harder to test and reuse.

        Args:
            image_path: Absolute path to an image file.

        Returns:
            Tuple of (tensor, valid_width).
        """
        warnings.warn(
            "ImagePreprocessor.preprocess(image_path) is deprecated. "
            "Use load_image(path) followed by preprocess_pil(pil_img) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        pil_img = load_image(image_path)
        return self.preprocess_pil(pil_img)

    # -----------------------------------------------------------------------
    # Batch API — accepts both paths and PIL.Image objects
    # -----------------------------------------------------------------------

    def preprocess_batch(
        self,
        image_sources: List[Union[str, Image.Image]],
    ) -> List[Tuple[torch.Tensor, int]]:
        """Preprocess a batch of images.

        Args:
            image_sources: A list of PIL.Image objects or filesystem paths (str).
                           Mixing both types is supported.

        Returns:
            List of (tensor, valid_width) tuples, one per input image.
        """
        results = []
        for src in image_sources:
            if isinstance(src, str):
                pil_img = load_image(src)
            else:
                pil_img = src
            results.append(self.preprocess_pil(pil_img))
        return results


# ---------------------------------------------------------------------------
# Way C: Line Segmentation & Way A: Enhanced Hand-crafted Hybrid Features
# ---------------------------------------------------------------------------

def segment_lines(pil_img: Image.Image) -> List[Image.Image]:
    """Segment a multi-line image into individual horizontal text lines.

    Uses an inverse Otsu binarization and horizontal projection profile to detect
    blank vertical spacing between text segments.
    """
    try:
        # Convert to grayscale numpy array
        img_gray = np.array(pil_img.convert("L"))
        h, w = img_gray.shape
        if h == 0 or w == 0:
            return [pil_img]

        # Binarize and invert (so text is 255 (white) and background is 0 (black))
        _, thresh = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Horizontal projection profile (sum white pixels along each row)
        row_sums = np.sum(thresh, axis=1)

        # Smooth using moving average to avoid spurious peaks/noise in margins
        window_size = 5
        if len(row_sums) > window_size:
            row_sums = np.convolve(row_sums, np.ones(window_size) / window_size, mode="same")

        max_sum = np.max(row_sums)
        # Background threshold: rows with sum <= 1% of the peak are blank gaps
        line_threshold = max(5.0, max_sum * 0.01)
        is_text = row_sums > line_threshold

        lines = []
        in_line = False
        start_idx = 0

        for i, val in enumerate(is_text):
            if val and not in_line:
                start_idx = i
                in_line = True
            elif not val and in_line:
                end_idx = i
                # Filter out lines that are too thin to be actual text (e.g. noise/ruled lines)
                if end_idx - start_idx >= 8:
                    lines.append((start_idx, end_idx))
                in_line = False

        if in_line:
            end_idx = len(is_text)
            if end_idx - start_idx >= 8:
                lines.append((start_idx, end_idx))

        if not lines:
            return [pil_img]

        # Crop original PIL Image horizontally for each line
        cropped_lines = []
        for start, end in lines:
            # Add vertical padding for safety (stops ascenders/descenders from clipping)
            pad = 4
            y0 = max(0, start - pad)
            y1 = min(h, end + pad)
            line_crop = pil_img.crop((0, y0, w, y1))
            cropped_lines.append(line_crop)

        logger.info("Line Segmentation complete: detected %d text lines.", len(cropped_lines))
        return cropped_lines

    except Exception as exc:
        logger.warning("Line Segmentation failed: %s. Falling back to full image.", exc)
        return [pil_img]



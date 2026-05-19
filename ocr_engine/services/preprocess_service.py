from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms

from ..torch_models.ocr_model import IMG_HEIGHT, IMG_WIDTH


class ImagePreprocessor:
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

    def _enhance(self, pil_img: Image.Image) -> Image.Image:
        img_np = np.array(pil_img.convert("L"))

        if self.denoise:
            img_np = cv2.medianBlur(img_np, 3)

        if self.enhance_contrast:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_np = clahe.apply(img_np)

        if self.binarize:
            _, img_np = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return Image.fromarray(img_np).convert("RGB")

    def preprocess(self, image_path: str) -> Tuple[torch.Tensor, int]:
        img = Image.open(image_path).convert("RGB")
        original_w, original_h = img.size

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

    def preprocess_batch(self, image_paths: List[str]) -> List[Tuple[torch.Tensor, int]]:
        return [self.preprocess(p) for p in image_paths]

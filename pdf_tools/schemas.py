"""
Input validation schemas for pdf_tools operations.

Uses Python dataclasses for clean, typed input contracts.
Views should instantiate and validate these before calling services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .exceptions import PageRangeError


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

VALID_ANGLES = (90, 180, 270)
VALID_POSITIONS = ("center", "top-left", "top-right", "bottom-left", "bottom-right")


def _validate_page_list(pages: List[int], page_count: int, field_name: str = "pages") -> None:
    """Validate that all page numbers are within [1, page_count]."""
    if not pages:
        raise PageRangeError(f"'{field_name}' must not be empty.")
    for p in pages:
        if not isinstance(p, int) or p < 1 or p > page_count:
            raise PageRangeError(
                f"Page number {p!r} in '{field_name}' is out of range [1, {page_count}]."
            )


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

@dataclass
class MergeSchema:
    """Schema for merge operation."""
    file_paths: List[str]

    def validate(self) -> None:
        if not self.file_paths or len(self.file_paths) < 2:
            raise ValueError("At least 2 PDF files are required for merge.")


@dataclass
class SplitSchema:
    """Schema for split operation."""
    file_path: str
    # Ranges as list of (start, end) tuples (1-indexed, inclusive).
    # If None, split every page individually.
    ranges: Optional[List[tuple]] = None

    def validate(self, page_count: int) -> None:
        if self.ranges is not None:
            for start, end in self.ranges:
                if start < 1 or end > page_count or start > end:
                    raise PageRangeError(
                        f"Range ({start}, {end}) is invalid for a {page_count}-page document."
                    )


@dataclass
class ExtractSchema:
    """Schema for extraction operations."""
    file_path: str
    # None = all pages
    page_nums: Optional[List[int]] = None
    extract_text: bool = True
    extract_images: bool = False
    extract_metadata: bool = False

    def validate(self, page_count: int) -> None:
        if self.page_nums is not None:
            _validate_page_list(self.page_nums, page_count, "page_nums")


@dataclass
class ReorderSchema:
    """Schema for reorder operation."""
    file_path: str
    # 0-indexed page order array, e.g. [2, 0, 1] for a 3-page doc
    order: List[int]

    def validate(self, page_count: int) -> None:
        if sorted(self.order) != list(range(page_count)):
            raise PageRangeError(
                "order must be a permutation of page indices [0, page_count)."
            )


@dataclass
class DeleteSchema:
    """Schema for page deletion."""
    file_path: str
    pages: List[int]  # 1-indexed

    def validate(self, page_count: int) -> None:
        _validate_page_list(self.pages, page_count)
        if len(self.pages) >= page_count:
            raise PageRangeError("Cannot delete all pages from a PDF.")


@dataclass
class RotateSchema:
    """Schema for page rotation."""
    file_path: str
    pages: List[int]  # 1-indexed; empty list = all pages
    angle: int = 90

    def validate(self, page_count: int) -> None:
        if self.angle not in VALID_ANGLES:
            raise ValueError(f"angle must be one of {VALID_ANGLES}, got {self.angle}.")
        if self.pages:
            _validate_page_list(self.pages, page_count)


@dataclass
class CompressSchema:
    """Schema for compression."""
    file_path: str
    image_quality: int = 80  # 1-100
    linearize: bool = False

    def validate(self) -> None:
        if not (1 <= self.image_quality <= 100):
            raise ValueError("image_quality must be between 1 and 100.")


@dataclass
class TextWatermarkSchema:
    """Schema for text watermark."""
    file_path: str
    text: str
    opacity: float = 0.3
    position: str = "center"
    font_size: int = 48
    color: tuple = field(default_factory=lambda: (0.5, 0.5, 0.5))  # RGB 0-1
    pages: Optional[List[int]] = None  # None = all pages

    def validate(self, page_count: int) -> None:
        if not self.text.strip():
            raise ValueError("Watermark text must not be empty.")
        if not (0.0 <= self.opacity <= 1.0):
            raise ValueError("opacity must be between 0.0 and 1.0.")
        if self.position not in VALID_POSITIONS:
            raise ValueError(f"position must be one of {VALID_POSITIONS}.")
        if self.pages:
            _validate_page_list(self.pages, page_count)


@dataclass
class ImageWatermarkSchema:
    """Schema for image watermark."""
    file_path: str
    watermark_image_path: str
    opacity: float = 0.3
    position: str = "center"
    pages: Optional[List[int]] = None  # None = all pages

    def validate(self, page_count: int) -> None:
        if not (0.0 <= self.opacity <= 1.0):
            raise ValueError("opacity must be between 0.0 and 1.0.")
        if self.position not in VALID_POSITIONS:
            raise ValueError(f"position must be one of {VALID_POSITIONS}.")
        if self.pages:
            _validate_page_list(self.pages, page_count)


@dataclass
class EncryptSchema:
    """Schema for PDF encryption."""
    file_path: str
    user_password: str
    owner_password: str = ""
    # PyMuPDF permission flags (see fitz.PDF_PERM_*)
    permissions: int = -1  # -1 = all permissions

    def validate(self) -> None:
        if not self.user_password:
            raise ValueError("user_password must not be empty.")


@dataclass
class PreviewSchema:
    """Schema for preview generation."""
    file_path: str
    page_num: int = 1  # 1-indexed
    dpi: int = 150

    def validate(self, page_count: int) -> None:
        if not (1 <= self.page_num <= page_count):
            raise PageRangeError(
                f"page_num {self.page_num} out of range [1, {page_count}]."
            )
        if self.dpi < 36 or self.dpi > 600:
            raise ValueError("dpi must be between 36 and 600.")

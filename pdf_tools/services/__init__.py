"""
pdf_tools/services package.

Re-exports all public service functions for convenient imports:

    from pdf_tools.services import merge_pdfs, split_pdf, ...
"""

from .merge_service import merge_pdfs
from .split_service import split_pdf, split_pdf_by_ranges_str, split_all_pages
from .extract_service import extract_text, extract_images, extract_metadata
from .reorder_service import reorder_pages
from .delete_service import delete_pages
from .rotate_service import rotate_pages
from .compress_service import compress_pdf
from .watermark_service import add_text_watermark, add_image_watermark
from .encrypt_service import encrypt_pdf, decrypt_pdf
from .preview_service import generate_preview, generate_all_previews

__all__ = [
    # Merge
    "merge_pdfs",
    # Split
    "split_pdf",
    "split_pdf_by_ranges_str",
    "split_all_pages",
    # Extract
    "extract_text",
    "extract_images",
    "extract_metadata",
    # Reorder
    "reorder_pages",
    # Delete
    "delete_pages",
    # Rotate
    "rotate_pages",
    # Compress
    "compress_pdf",
    # Watermark
    "add_text_watermark",
    "add_image_watermark",
    # Encrypt
    "encrypt_pdf",
    "decrypt_pdf",
    # Preview
    "generate_preview",
    "generate_all_previews",
]

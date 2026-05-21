"""Extract service — extract text, images, and metadata from a PDF."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import ExtractError
from .utils import open_pdf, ensure_output_dir, get_output_path

logger = logging.getLogger(__name__)


def extract_text(
    file_path: str,
    page_nums: Optional[List[int]] = None,
    mode: str = "text",
) -> Dict:
    """Extract text content from a PDF.

    Args:
        file_path: Absolute path to the source PDF.
        page_nums: 1-indexed list of pages to extract. None = all pages.
        mode: fitz extraction mode: "text", "blocks", "words", "html", "dict".
              Defaults to "text" for plain text output.

    Returns:
        Dict with keys:
            - "pages": list of {"page": int, "content": str/dict}
            - "full_text": concatenated plain text (only if mode == "text")
            - "page_count": int
            - "file_path": str

    Raises:
        ExtractError: if extraction fails.
    """
    logger.info("Extracting text from %s (mode=%s)", file_path, mode)

    src = open_pdf(file_path)
    page_count = src.page_count

    # Determine which pages to process (0-indexed)
    if page_nums is None:
        pages_0 = list(range(page_count))
    else:
        pages_0 = [p - 1 for p in page_nums if 1 <= p <= page_count]

    result_pages = []
    full_text_parts = []

    try:
        for i in pages_0:
            page = src[i]
            try:
                content = page.get_text(mode)
            except Exception as exc:
                logger.warning("Failed to extract text from page %d: %s", i + 1, exc)
                content = ""

            result_pages.append({"page": i + 1, "content": content})
            if mode == "text" and isinstance(content, str):
                full_text_parts.append(content)

    except Exception as exc:
        raise ExtractError(f"Text extraction failed: {exc}") from exc
    finally:
        src.close()

    result = {
        "pages": result_pages,
        "page_count": page_count,
        "file_path": file_path,
    }
    if mode == "text":
        result["full_text"] = "\n\n".join(full_text_parts)

    logger.info("Text extraction complete: %d pages processed", len(result_pages))
    return result


def extract_images(
    file_path: str,
    page_nums: Optional[List[int]] = None,
    output_dir: Optional[str] = None,
    min_width: int = 50,
    min_height: int = 50,
) -> List[str]:
    """Extract embedded images from a PDF and save them to disk.

    Args:
        file_path: Absolute path to the source PDF.
        page_nums: 1-indexed page list. None = all pages.
        output_dir: Directory to save images. Auto-created if None.
        min_width: Skip images narrower than this (filters icons/artifacts).
        min_height: Skip images shorter than this.

    Returns:
        List of absolute paths to saved image files.

    Raises:
        ExtractError: if image extraction fails.
    """
    if output_dir is None:
        output_dir = ensure_output_dir("extracted_images")
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Extracting images from %s", file_path)

    src = open_pdf(file_path)
    page_count = src.page_count

    if page_nums is None:
        pages_0 = list(range(page_count))
    else:
        pages_0 = [p - 1 for p in page_nums if 1 <= p <= page_count]

    saved_paths: List[str] = []
    image_counter = 0

    try:
        for i in pages_0:
            page = src[i]
            image_list = page.get_images(full=True)

            for img_info in image_list:
                xref = img_info[0]
                try:
                    base_image = src.extract_image(xref)
                    img_bytes = base_image["image"]
                    img_ext = base_image.get("ext", "png")
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    if width < min_width or height < min_height:
                        logger.debug(
                            "Skipping small image (xref=%d) %dx%d on page %d",
                            xref, width, height, i + 1,
                        )
                        continue

                    image_counter += 1
                    img_filename = f"page{i + 1:04d}_img{image_counter:04d}.{img_ext}"
                    img_path = os.path.join(output_dir, img_filename)

                    with open(img_path, "wb") as f:
                        f.write(img_bytes)

                    saved_paths.append(img_path)
                    logger.debug("Saved image → %s (%dx%d)", img_path, width, height)

                except Exception as exc:
                    logger.warning(
                        "Failed to extract image xref=%d on page %d: %s", xref, i + 1, exc
                    )

    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError(f"Image extraction failed: {exc}") from exc
    finally:
        src.close()

    logger.info("Image extraction complete: %d images saved", len(saved_paths))
    return saved_paths


def extract_metadata(file_path: str) -> Dict:
    """Extract document metadata from a PDF.

    Returns:
        Dict containing standard PDF metadata fields plus page_count.

    Raises:
        ExtractError: if metadata extraction fails.
    """
    logger.info("Extracting metadata from %s", file_path)

    try:
        src = open_pdf(file_path)
        meta = src.metadata or {}
        page_count = src.page_count
        is_encrypted = src.is_encrypted

        # Add extra info
        meta["page_count"] = page_count
        meta["is_encrypted"] = is_encrypted
        meta["file_path"] = file_path
        meta["file_size_bytes"] = os.path.getsize(file_path) if os.path.isfile(file_path) else None

        src.close()
        logger.info("Metadata extracted: %d fields", len(meta))
        return meta

    except Exception as exc:
        raise ExtractError(f"Metadata extraction failed: {exc}") from exc

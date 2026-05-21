"""Encrypt PDF service — add password protection and permission settings."""

from __future__ import annotations

import logging
from typing import Optional

import fitz  # PyMuPDF

from pdf_tools.exceptions import EncryptError
from .utils import open_pdf, get_output_path

logger = logging.getLogger(__name__)

# PyMuPDF permission bit constants
# Reference: https://pymupdf.readthedocs.io/en/latest/document.html#Document.save
PERM_PRINT = fitz.PDF_PERM_PRINT
PERM_COPY = fitz.PDF_PERM_COPY
PERM_ANNOTATE = fitz.PDF_PERM_ANNOTATE
PERM_FORM = fitz.PDF_PERM_FORM
PERM_ACCESSIBILITY = fitz.PDF_PERM_ACCESSIBILITY
PERM_ASSEMBLE = fitz.PDF_PERM_ASSEMBLE
PERM_PRINT_HQ = fitz.PDF_PERM_PRINT_HQ
PERM_ALL = -1  # All permissions granted


def encrypt_pdf(
    file_path: str,
    user_password: str,
    owner_password: Optional[str] = None,
    permissions: int = PERM_ALL,
    encryption_method: int = fitz.PDF_ENCRYPT_AES_256,
    output_path: Optional[str] = None,
) -> str:
    """Encrypt a PDF with password protection and optional permissions.

    Args:
        file_path: Absolute path to source PDF.
        user_password: Password required to open/view the document.
        owner_password: Password granting full control. Defaults to user_password.
        permissions: Bitfield of allowed operations. Use PERM_* constants.
                     -1 (PERM_ALL) means all permissions granted.
        encryption_method: PyMuPDF encryption algorithm.
                           Default: AES-256 (most secure).
        output_path: Destination path. Auto-generated if None.

    Returns:
        Absolute path to the encrypted output PDF.

    Raises:
        EncryptError: if encryption fails.
        ValueError: if user_password is empty.
    """
    if not user_password:
        raise EncryptError("user_password must not be empty.")

    if owner_password is None:
        owner_password = user_password

    if output_path is None:
        output_path = get_output_path("encrypted")

    logger.info("Encrypting %s with AES-256", file_path)

    src = open_pdf(file_path)

    try:
        src.save(
            output_path,
            encryption=encryption_method,
            user_pw=user_password,
            owner_pw=owner_password,
            permissions=permissions,
            garbage=3,
            deflate=True,
        )
        logger.info("Encryption complete → %s", output_path)
    except Exception as exc:
        raise EncryptError(f"Encryption failed: {exc}") from exc
    finally:
        src.close()

    return output_path


def decrypt_pdf(
    file_path: str,
    password: str,
    output_path: Optional[str] = None,
) -> str:
    """Remove encryption from a PDF (requires owner password).

    Args:
        file_path: Absolute path to encrypted source PDF.
        password: Owner password to authenticate.
        output_path: Destination path. Auto-generated if None.

    Returns:
        Absolute path to the decrypted output PDF.

    Raises:
        EncryptError: if decryption fails.
    """
    if output_path is None:
        output_path = get_output_path("decrypted")

    # open_pdf handles authentication; raises EncryptedPDFError on wrong password
    src = open_pdf(file_path, password=password)

    try:
        src.save(
            output_path,
            encryption=fitz.PDF_ENCRYPT_NONE,
            garbage=3,
            deflate=True,
        )
        logger.info("Decryption complete → %s", output_path)
    except Exception as exc:
        raise EncryptError(f"Decryption failed: {exc}") from exc
    finally:
        src.close()

    return output_path

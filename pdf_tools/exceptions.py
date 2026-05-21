"""Custom exceptions for pdf_tools app."""


class PDFToolsError(Exception):
    """Base exception for all pdf_tools errors."""


class InvalidPDFError(PDFToolsError):
    """Raised when a file is not a valid PDF or cannot be opened."""


class PageRangeError(PDFToolsError):
    """Raised when page numbers or ranges are invalid."""


class EncryptedPDFError(PDFToolsError):
    """Raised when attempting to process a password-protected PDF without credentials."""


class MergeError(PDFToolsError):
    """Raised when PDF merge operation fails."""


class SplitError(PDFToolsError):
    """Raised when PDF split operation fails."""


class ExtractError(PDFToolsError):
    """Raised when extraction (text/images/metadata) fails."""


class WatermarkError(PDFToolsError):
    """Raised when watermarking operation fails."""


class EncryptError(PDFToolsError):
    """Raised when encryption operation fails."""


class CompressError(PDFToolsError):
    """Raised when compression operation fails."""


class PreviewError(PDFToolsError):
    """Raised when preview/thumbnail generation fails."""


class ReorderError(PDFToolsError):
    """Raised when page reorder operation fails."""


class DeletePageError(PDFToolsError):
    """Raised when page deletion operation fails."""


class RotateError(PDFToolsError):
    """Raised when page rotation operation fails."""

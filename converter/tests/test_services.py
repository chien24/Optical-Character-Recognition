"""
converter/tests/test_services.py

Unit tests for the converter service layer.

We test each converter in isolation by creating a real temporary file,
running the converter, and asserting on the output.  No Django DB is
needed for pure service tests — those that do need the DB use
``TestCase``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from converter.services.exceptions import (
    ConversionFailedError,
    FileMissingError,
    UnsupportedFormatError,
)
from converter.services.registry import ConverterRegistry


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def setup_method(self):
        """Fresh registry per test so registrations don't leak."""
        self.reg = ConverterRegistry()

    def test_unsupported_format_raises(self):
        with pytest.raises(UnsupportedFormatError):
            self.reg.get("xyz", "abc")

    def test_is_supported_false_when_empty(self):
        assert self.reg.is_supported("pdf", "txt") is False

    def test_register_and_retrieve(self):
        from converter.services.base import BaseConverter
        from pathlib import Path

        class DummyConverter(BaseConverter):
            source_format = "foo"
            target_format = "bar"

            def convert(self, i: Path, o: Path) -> Path:
                return o

        inst = DummyConverter()
        self.reg.register(inst)
        assert self.reg.is_supported("foo", "bar")
        assert self.reg.get("foo", "bar") is inst

    def test_duplicate_registration_raises(self):
        from converter.services.base import BaseConverter

        class DummyConverter(BaseConverter):
            source_format = "dup"
            target_format = "dup"

            def convert(self, i: Path, o: Path) -> Path:
                return o

        self.reg.register(DummyConverter())
        with pytest.raises(ValueError):
            self.reg.register(DummyConverter())

    def test_supported_targets_for(self):
        from converter.services.base import BaseConverter

        class C1(BaseConverter):
            source_format = "src"
            target_format = "a"

            def convert(self, i, o):
                return o

        class C2(BaseConverter):
            source_format = "src"
            target_format = "b"

            def convert(self, i, o):
                return o

        self.reg.register(C1())
        self.reg.register(C2())
        assert self.reg.supported_targets_for("src") == ["a", "b"]


# ---------------------------------------------------------------------------
# PDF → Text
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("fitz"),
    reason="PyMuPDF not installed",
)
class TestPdfToText:
    def _make_pdf(self, tmp: Path, text: str = "Hello World") -> Path:
        """Create a minimal single-page PDF with given text."""
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        pdf_path = tmp / "input.pdf"
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    def test_pdf_to_text_success(self, tmp_path):
        from converter.services.pdf_service import PdfToTextConverter

        pdf = self._make_pdf(tmp_path, "Test page content")
        out = tmp_path / "out.txt"
        result = PdfToTextConverter().convert(pdf, out)
        assert result == out
        content = out.read_text(encoding="utf-8")
        assert "Test page content" in content

    def test_pdf_to_text_missing_file(self, tmp_path):
        from converter.services.pdf_service import PdfToTextConverter

        with pytest.raises(FileMissingError):
            PdfToTextConverter().convert(tmp_path / "nope.pdf", tmp_path / "out.txt")


# ---------------------------------------------------------------------------
# PDF → Markdown
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("fitz"),
    reason="PyMuPDF not installed",
)
class TestPdfToMarkdown:
    def _make_pdf(self, tmp: Path) -> Path:
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Section Header", fontsize=22)
        page.insert_text((72, 120), "Body text content here.", fontsize=11)
        pdf_path = tmp / "input.pdf"
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    def test_produces_markdown_file(self, tmp_path):
        from converter.services.pdf_service import PdfToMarkdownConverter

        pdf = self._make_pdf(tmp_path)
        out = tmp_path / "out.md"
        result = PdfToMarkdownConverter().convert(pdf, out)
        assert result == out
        content = out.read_text(encoding="utf-8")
        # Should produce some heading marker
        assert "#" in content

    def test_missing_file_raises(self, tmp_path):
        from converter.services.pdf_service import PdfToMarkdownConverter

        with pytest.raises(FileMissingError):
            PdfToMarkdownConverter().convert(tmp_path / "nope.pdf", tmp_path / "out.md")


# ---------------------------------------------------------------------------
# Image → PDF
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("PIL"),
    reason="Pillow not installed",
)
class TestImageToPdf:
    def _make_png(self, tmp: Path) -> Path:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        p = tmp / "test.png"
        img.save(str(p))
        return p

    def test_png_to_pdf(self, tmp_path):
        from converter.services.image_service import ImageToPdfConverter

        png = self._make_png(tmp_path)
        out = tmp_path / "out.pdf"
        conv = ImageToPdfConverter(source_fmt="png")
        result = conv.convert(png, out)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_missing_image_raises(self, tmp_path):
        from converter.services.image_service import ImageToPdfConverter

        with pytest.raises(FileMissingError):
            ImageToPdfConverter(source_fmt="png").convert(
                tmp_path / "nope.png", tmp_path / "out.pdf"
            )


# ---------------------------------------------------------------------------
# Markdown → Text
# ---------------------------------------------------------------------------


class TestMarkdownToText:
    def test_strips_headings(self, tmp_path):
        from converter.services.markdown_service import MarkdownToTextConverter

        md = tmp_path / "in.md"
        md.write_text("# Heading\n\nParagraph text.", encoding="utf-8")
        out = tmp_path / "out.txt"
        MarkdownToTextConverter().convert(md, out)
        content = out.read_text(encoding="utf-8")
        assert "#" not in content
        assert "Heading" in content
        assert "Paragraph text." in content

    def test_missing_file_raises(self, tmp_path):
        from converter.services.markdown_service import MarkdownToTextConverter

        with pytest.raises(FileMissingError):
            MarkdownToTextConverter().convert(tmp_path / "nope.md", tmp_path / "out.txt")


# ---------------------------------------------------------------------------
# DOCX → PDF (integration-style, requires LibreOffice)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    __import__("shutil").which("soffice") is None,
    reason="LibreOffice (soffice) not on PATH",
)
class TestDocxToPdf:
    def _make_docx(self, tmp: Path) -> Path:
        from docx import Document

        doc = Document()
        doc.add_paragraph("Hello from python-docx")
        p = tmp / "test.docx"
        doc.save(str(p))
        return p

    def test_docx_to_pdf(self, tmp_path):
        from converter.services.docx_service import DocxToPdfConverter

        docx = self._make_docx(tmp_path)
        out = tmp_path / "out.pdf"
        DocxToPdfConverter().convert(docx, out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_missing_docx_raises(self, tmp_path):
        from converter.services.docx_service import DocxToPdfConverter

        with pytest.raises(FileMissingError):
            DocxToPdfConverter().convert(tmp_path / "nope.docx", tmp_path / "out.pdf")

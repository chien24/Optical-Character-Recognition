"""
converter/forms.py

Forms for the converter app.
"""

from __future__ import annotations

from django import forms

# Supported source-file extensions that the UI accepts.
_ALLOWED_EXTENSIONS = {
    "pdf", "docx",
    "png", "jpg", "jpeg", "bmp", "webp", "tiff",
    "md",
}

# Choices shown to the user in the target-format dropdown.
TARGET_FORMAT_CHOICES = [
    ("pdf",  "PDF Document (.pdf)"),
    ("txt",  "Plain Text (.txt)"),
    ("md",   "Markdown (.md)"),
]


class ConversionForm(forms.Form):
    """Upload form: select a file and the desired output format."""

    file = forms.FileField(
        label="File to convert",
        help_text=(
            "Supported input formats: PDF, DOCX, PNG, JPG, JPEG, BMP, WEBP, TIFF, MD."
        ),
    )
    target_format = forms.ChoiceField(
        choices=TARGET_FORMAT_CHOICES,
        label="Convert to",
    )

    # ------------------------------------------------------------------
    # Custom validation
    # ------------------------------------------------------------------

    def clean_file(self) -> forms.FileField:
        """Reject files with unsupported extensions."""
        uploaded = self.cleaned_data.get("file")
        if uploaded is None:
            raise forms.ValidationError("No file was submitted.")

        ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
        if ext not in _ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                f"Unsupported file type '.{ext}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}."
            )
        return uploaded

    def clean(self) -> dict:
        """Cross-field: make sure the conversion pair is actually supported."""
        cleaned = super().clean()
        uploaded = cleaned.get("file")
        target = cleaned.get("target_format")

        if uploaded and target:
            from converter.services import registry

            src_ext = uploaded.name.rsplit(".", 1)[-1].lower()
            if not registry.is_supported(src_ext, target):
                available = registry.supported_targets_for(src_ext)
                msg = (
                    f"Converting '{src_ext.upper()}' → '{target.upper()}' is not "
                    "supported."
                )
                if available:
                    msg += f" Available targets for {src_ext.upper()}: {', '.join(t.upper() for t in available)}."
                raise forms.ValidationError(msg)

        return cleaned

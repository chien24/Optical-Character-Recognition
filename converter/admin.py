"""
converter/admin.py

Register ConversionJob in the Django admin for easy debugging.
"""

from django.contrib import admin

from .models import ConversionJob


@admin.register(ConversionJob)
class ConversionJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_format",
        "target_format",
        "status",
        "input_file",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "source_format", "target_format")
    search_fields = ("input_file__original_name",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

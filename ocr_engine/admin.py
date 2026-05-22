from django.contrib import admin
from .models import OCRResult


@admin.register(OCRResult)
class OCRResultAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "pages", "confidence", "created_at")
    list_filter = ("job__job_type", "job__status")
    readonly_fields = ("created_at", "updated_at", "metadata")
    search_fields = ("job__id", "text")
    raw_id_fields = ("job",)

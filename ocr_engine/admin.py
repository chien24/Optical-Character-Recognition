from django.contrib import admin
from .models import OCRResult


@admin.register(OCRResult)
class OCRResultAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "pages", "confidence", "created_at")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("job__id",)
from django.contrib import admin

# Register your models here.

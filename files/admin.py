from django.contrib import admin
from .models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
	list_display = ("id", "original_name", "owner", "status", "created_at")
	readonly_fields = ("created_at", "updated_at")


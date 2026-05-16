from django.contrib import admin
from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "job_type", "status", "created_by", "created_at")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at")
    search_fields = ("job_type", "status")
from django.contrib import admin

# Register your models here.

"""
URL configuration for OCR project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", include("core.urls", namespace="core")),
    path("admin/", admin.site.urls),
    path("files/", include("files.urls", namespace="files")),
    path("users/", include("users.urls", namespace="users")),
    path("ocr/", include("ocr_engine.urls", namespace="ocr_engine")),
    path("processing/", include("processing.urls", namespace="processing")),
    path("converter/", include("converter.urls", namespace="converter")),
    path("translator/", include("translator.urls", namespace="translator")),
    path("pdf-tools/", include("pdf_tools.urls", namespace="pdf_tools")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

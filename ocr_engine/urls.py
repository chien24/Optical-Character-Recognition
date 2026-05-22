"""
ocr_engine/urls.py
"""
from django.urls import path
from . import views

app_name = "ocr_engine"

urlpatterns = [
    # HTML form handler: dashboard posts here
    path("run/", views.start_ocr, name="start_ocr"),
    # Result page: view OCR output for a job
    path("<int:pk>/", views.view_result, name="view_result"),
    # JSON API endpoint (legacy / programmatic use)
    path("api/upload/", views.upload_and_run_ocr, name="ocr_upload"),
]

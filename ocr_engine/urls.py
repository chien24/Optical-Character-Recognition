from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_and_run_ocr, name="ocr_upload"),
]

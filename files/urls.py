from django.urls import path
from . import views

app_name = "files"

urlpatterns = [
    path("upload/", views.upload_view, name="upload"),
    path("upload/success/", views.upload_success, name="upload_success"),
]

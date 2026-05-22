"""
processing/urls.py
"""
from django.urls import path
from . import views

app_name = "processing"

urlpatterns = [
    path("status/<int:pk>/", views.job_status, name="job_status"),
    path("delete/<int:pk>/", views.delete_job, name="delete_job"),
]

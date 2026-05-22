"""
converter/urls.py
"""

from django.urls import path

from . import views

app_name = "converter"

urlpatterns = [
    path("", views.convert, name="convert"),
    path("<int:pk>/", views.conversion_detail, name="conversion_detail"),
]

from django.urls import path
from . import views

app_name = "pdf_tools"

urlpatterns = [
    path("", views.index, name="index"),
    path("merge/", views.merge, name="merge"),
    path("split/", views.split, name="split"),
]

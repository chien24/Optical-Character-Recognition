from django.urls import path
from . import views

app_name = "pdf_tools"

urlpatterns = [
    path("", views.index, name="index"),
    # Core tools
    path("merge/", views.merge, name="merge"),
    path("split/", views.split, name="split"),
    path("extract/", views.extract, name="extract"),
    # Page management
    path("reorder/", views.reorder, name="reorder"),
    path("delete-pages/", views.delete_pages_view, name="delete_pages"),
    path("rotate/", views.rotate, name="rotate"),
    # Optimization & security
    path("compress/", views.compress, name="compress"),
    path("watermark/", views.watermark, name="watermark"),
    path("encrypt/", views.encrypt, name="encrypt"),
    # Preview
    path("preview/", views.preview, name="preview"),
]

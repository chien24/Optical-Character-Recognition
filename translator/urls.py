from django.urls import path
from . import views

app_name = "translator"

urlpatterns = [
    path("api/translate/", views.translate_api, name="translate_api"),
    path("", views.index, name="index"),
]

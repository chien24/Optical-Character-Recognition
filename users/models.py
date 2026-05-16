from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user using AbstractUser. Keep minimal fields as required.

    Email is required and unique. Username remains for compatibility.
    """

    email = models.EmailField(unique=True)

    # Optional avatar
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    def __str__(self):  # pragma: no cover - trivial
        return self.username
from django.db import models

# Create your models here.

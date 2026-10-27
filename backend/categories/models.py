from django.db import models
from core.models import BaseModel

class Category(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self):
        return self.name

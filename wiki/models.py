from django.conf import settings
from django.db import models


class WikiPage(models.Model):
    """Evergreen reference: plants, beds, equipment, how-tos. Body is Markdown."""

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class WikiRevision(models.Model):
    """Previous version of a page, kept every time it's saved."""

    page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name="revisions")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} @ {self.created_at:%Y-%m-%d %H:%M}"

from django.conf import settings
from django.db import models
from django.utils import timezone


class Post(models.Model):
    """A dated journal / blog entry. Shows up on its day in the almanac."""

    title = models.CharField(max_length=200)
    # The greenhouse day this entry is about (not necessarily when it was typed).
    date = models.DateField(default=timezone.localdate, db_index=True)
    body = models.TextField(blank=True)  # Markdown, may contain photos and [[wiki links]]
    published = models.BooleanField(default=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} {self.title}"


class Photo(models.Model):
    """An uploaded picture, resized and stored on the data drive (MEDIA_ROOT)."""

    file = models.CharField(max_length=300)  # path relative to MEDIA_ROOT
    original_name = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=300, blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    taken_at = models.DateTimeField(null=True, blank=True)  # from EXIF when present
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-uploaded_at"]

    @property
    def url(self):
        return "/" + settings.MEDIA_URL.lstrip("/") + self.file

    def __str__(self):
        return self.original_name or self.file

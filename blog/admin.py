from django.contrib import admin

from .models import Photo, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "published", "updated_at")
    list_filter = ("published",)
    search_fields = ("title", "body")
    date_hierarchy = "date"


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("original_name", "file", "width", "height", "uploaded_at")
    readonly_fields = ("file", "width", "height", "taken_at", "uploaded_at", "uploaded_by")

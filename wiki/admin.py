from django.contrib import admin

from .models import WikiPage, WikiRevision


class WikiRevisionInline(admin.TabularInline):
    model = WikiRevision
    extra = 0
    readonly_fields = ("title", "body", "created_at", "created_by")


@admin.register(WikiPage)
class WikiPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "updated_at")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [WikiRevisionInline]

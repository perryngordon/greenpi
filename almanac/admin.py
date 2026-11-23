from django.contrib import admin

from .models import AlmanacEvent


@admin.register(AlmanacEvent)
class AlmanacEventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "yearly", "kind")
    list_filter = ("kind", "yearly")
    search_fields = ("title", "notes")

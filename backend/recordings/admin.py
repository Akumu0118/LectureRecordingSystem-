from django.contrib import admin

from .models import Recording


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "status", "duration", "created_at")
    list_filter = ("status", "subject")
    search_fields = ("title", "subject", "notes")
    readonly_fields = ("id", "created_at", "updated_at", "error")

import uuid
from pathlib import Path

from django.db import models


def original_upload_path(instance, filename):
    ext = Path(filename).suffix.lower() or ".bin"
    return f"recordings/{instance.id}/original{ext}"


class Recording(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    original = models.FileField(upload_to=original_upload_path)
    # Relative path inside MEDIA_ROOT, e.g. recordings/<id>/processed.wav
    processed = models.CharField(max_length=500, blank=True)

    duration = models.FloatField(null=True, blank=True, help_text="Seconds")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPLOADED
    )
    error = models.TextField(blank=True, help_text="Technical error detail (internal)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or str(self.id)

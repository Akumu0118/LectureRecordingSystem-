import shutil
from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Recording


@receiver(post_delete, sender=Recording)
def delete_recording_files(sender, instance, **kwargs):
    """Remove the recording's whole folder (original, processed, cached exports)."""
    folder = Path(settings.MEDIA_ROOT) / "recordings" / str(instance.id)
    shutil.rmtree(folder, ignore_errors=True)

"""Glue between the Django models and the framework-free pipeline."""
import logging
import shutil
from pathlib import Path

from django.conf import settings

from voiceclean import pipeline

from .models import Recording

logger = logging.getLogger(__name__)

FRIENDLY_PROCESSING_ERROR = (
    "Processing failed. Your original recording is safe. Retry or download it."
)


def recording_dir(recording: Recording) -> Path:
    return Path(settings.MEDIA_ROOT) / "recordings" / str(recording.id)


def processed_path(recording: Recording) -> Path | None:
    if not recording.processed:
        return None
    path = Path(settings.MEDIA_ROOT) / recording.processed
    return path if path.exists() else None


def clear_exports(recording: Recording) -> None:
    shutil.rmtree(recording_dir(recording) / "exports", ignore_errors=True)


def process_recording(recording: Recording) -> Recording:
    """Run the pipeline synchronously and persist the outcome."""
    recording.status = Recording.Status.PROCESSING
    recording.error = ""
    recording.save(update_fields=["status", "error", "updated_at"])
    clear_exports(recording)

    try:
        final = pipeline.process(
            recording.original.path, recording_dir(recording), out_name="processed"
        )
        recording.processed = str(Path("recordings") / str(recording.id) / final.name)
        recording.duration = pipeline.wav_duration(final)
        recording.status = Recording.Status.DONE
    except pipeline.PipelineError as exc:
        logger.warning("Pipeline failed for %s: %s", recording.id, exc)
        recording.status = Recording.Status.FAILED
        recording.error = str(exc)
    except Exception as exc:  # never leave a recording stuck in "processing"
        logger.exception("Unexpected failure processing %s", recording.id)
        recording.status = Recording.Status.FAILED
        recording.error = f"{type(exc).__name__}: {exc}"

    recording.save()
    return recording

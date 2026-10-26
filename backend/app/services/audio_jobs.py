"""Fixed, bounded non-AI audio jobs. Original bytes are never rewritten."""
from functools import lru_cache
import logging
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import BoundedSemaphore
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AudioFile, FileRole, RecordingStatus
from app.schemas.audio_version import AudioVersion
from app.services.recording_storage import RecordingStorage
from app.services.reference_storage import FORMATS
from app.services.recordings import original_file, require_recording

logger = logging.getLogger(__name__)
PRESETS = {
    FileRole.EXPORTED: ("speech-mp3-v1.mp3", "exports", ".mp3", "audio/mpeg",
                        ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "32000", "-ac", "1", "-f", "mp3"]),
    FileRole.PROCESSED: ("speech-enhance-v1.wav", "processed", ".wav", "audio/wav",
                         ["-af", "highpass=f=80,lowpass=f=7000,afftdn=nr=6:nf=-35,loudnorm=I=-18:TP=-1.5:LRA=11",
                          "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1", "-f", "wav"]),
}


@lru_cache(maxsize=8)
def job_slots(count):
    # One process-local pool; use one Uvicorn worker for this local MVP.
    return BoundedSemaphore(count)


def version_read(recording_id, file, storage):
    path = storage.path(file.storage_path)
    base = f"/api/recordings/{recording_id}/versions/{file.id}"
    return AudioVersion(**{name: getattr(file, name) for name in AudioVersion.model_fields
                           if name not in {"audio_url", "download_url", "available", "preset"}},
                        audio_url=base + "/audio", download_url=base + "/download",
                        available=path.is_file(),
                        preset=PRESETS[file.file_role][0].rsplit('.', 1)[0]
                        if file.file_role in PRESETS and file.original_filename == PRESETS[file.file_role][0] else None)


def checked_file(file, storage):
    path = storage.path(file.storage_path)
    if not path.is_file():
        raise HTTPException(404, "Stored audio is missing")
    try:
        if path.stat().st_size != file.file_size_bytes:
            raise HTTPException(422, "Stored audio size does not match its metadata")
        if path.suffix.lower() not in FORMATS:
            raise HTTPException(415, "Stored audio format is unsupported")
        duration, _, _ = storage.probe(path, path.suffix.lower())
    except OSError:
        raise HTTPException(503, "Audio storage is unavailable") from None
    return path, duration


def convert(source, role, storage):
    settings = storage.settings
    executable = shutil.which(settings.ffmpeg_path)
    if not executable:
        raise HTTPException(503, "FFmpeg is unavailable; configure FFMPEG_PATH and restart the backend")
    name, directory, suffix, mime, options = PRESETS[role]
    relative = f"{directory}/{uuid4()}{suffix}"
    final = storage.path(relative)
    staged = None
    created = False
    try:
        final.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=final.parent, prefix=".job-", suffix=suffix, delete=False) as target:
            staged = Path(target.name)
        command = [executable, "-nostdin", "-hide_banner", "-v", "error", "-y", "-xerror",
                   "-threads", "1", "-filter_threads", "1", "-protocol_whitelist", "file",
                   "-format_whitelist", "wav,mp3,matroska,webm", "-i", str(source),
                   "-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "-1",
                   *options, "-threads", "1", "-fs", str(settings.max_generated_size_bytes), str(staged)]
        with tempfile.TemporaryFile() as errors:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=errors, timeout=settings.audio_job_timeout_seconds, check=False)
            if result.returncode:
                errors.seek(0)
                message = errors.read(16384).lower()
                if any(text in message for text in (b"no space left", b"not enough space", b"disk full")):
                    raise HTTPException(503, "Insufficient disk space for generated audio")
                raise HTTPException(422, "Audio generation failed; the original is unchanged")
        size = staged.stat().st_size
        if not 0 < size < settings.max_generated_size_bytes:
            raise HTTPException(413, "Generated audio exceeds the configured output limit")
        duration, rate, channels = storage.probe(staged, suffix)
        with final.open("xb") as target, staged.open("rb") as data:
            created = True
            shutil.copyfileobj(data, target, length=64 * 1024)
        return AudioFile(file_role=role, storage_path=relative, original_filename=name,
                         mime_type=mime, file_size_bytes=size, duration_seconds=duration,
                         sample_rate_hz=rate, channels=channels)
    except Exception as exc:
        if created:
            storage.cleanup(relative)
        if isinstance(exc, subprocess.TimeoutExpired):
            raise HTTPException(504, "Audio generation timed out; retry is safe") from None
        if isinstance(exc, OSError):
            raise HTTPException(503, "Audio generation storage or executable is unavailable; check free disk space") from None
        raise
    finally:
        if staged:
            try:
                staged.unlink(missing_ok=True)
            except OSError:
                logger.warning("Audio job staging cleanup pending: %s", staged.name)


def generate(db, recording_id, role, storage: RecordingStorage):
    value = require_recording(db, recording_id, lock=True)
    original = original_file(value)
    if value.status is not RecordingStatus.READY or original is None:
        raise HTTPException(409, "Save a ready original before generating audio")
    obsolete = []
    for existing in value.audio_files:
        if existing.file_role == role and existing.original_filename == PRESETS[role][0]:
            try:
                checked_file(existing, storage)
                response = version_read(value.id, existing, storage)
                db.rollback()  # Release the row lock on reuse.
                return response, False
            except HTTPException as exc:
                if exc.status_code not in {404, 415, 422}:
                    raise
                obsolete.append(existing)
    slots = job_slots(storage.settings.max_audio_jobs)
    if not slots.acquire(blocking=False):
        raise HTTPException(503, "Audio processing is busy; retry shortly")
    generated, committing, file_id = None, False, None
    old_paths = [file.storage_path for file in obsolete]
    try:
        source, source_duration = checked_file(original, storage)
        generated = convert(source, role, storage)
        # Detect truncated output even if FFmpeg's size limit produced a valid container.
        if abs(float(generated.duration_seconds) - float(source_duration)) > max(0.25, float(source_duration) * 0.001):
            raise HTTPException(422, "Generated audio duration does not match the original")
        generated.recording_id = value.id
        for file in obsolete:
            db.delete(file)
        db.add(generated)
        db.flush()
        file_id = generated.id
        response = version_read(value.id, generated, storage)
        committing = True
        db.commit()
    except Exception as exc:
        cleanup_safe = not committing or isinstance(exc, IntegrityError)
        try:
            db.rollback()
            if not cleanup_safe:
                cleanup_safe = db.scalar(select(AudioFile.id).where(AudioFile.id == file_id)) is None
        except Exception:
            logger.warning("Audio job commit could not be reconciled: %s", recording_id)
        if generated:
            if cleanup_safe:
                storage.cleanup(generated.storage_path)
            else:
                logger.warning("Generated audio retained after uncertain commit: %s", generated.storage_path)
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "Audio version could not be saved because related data changed") from None
        raise
    finally:
        slots.release()
    for path in old_paths:
        try:
            if db.scalar(select(AudioFile.id).where(AudioFile.storage_path == path)) is None:
                storage.cleanup(path)
        except Exception:
            db.rollback()
            logger.warning("Obsolete generated file cleanup pending: %s", path)
    return response, True

import logging
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import AudioFile, FileRole, Lecturer, VoiceSample
from app.schemas.voice_sample import ReferenceAudioRead, VoiceSampleDeleted, VoiceSampleRead
from app.services.lecturers import commit_change
from app.services.reference_storage import ReferenceStorage

logger = logging.getLogger(__name__)


def sample_read(sample: VoiceSample) -> VoiceSampleRead:
    return VoiceSampleRead(
        id=sample.id, lecturer_id=sample.lecturer_id, label=sample.label,
        created_at=sample.created_at, audio_file=ReferenceAudioRead.model_validate(sample.audio_file),
        audio_url=f"/api/lecturers/{sample.lecturer_id}/samples/{sample.id}/audio",
    )


def require_sample(db: Session, lecturer_id: UUID, sample_id: UUID) -> VoiceSample:
    sample = db.scalar(select(VoiceSample).options(joinedload(VoiceSample.audio_file)).where(
        VoiceSample.id == sample_id, VoiceSample.lecturer_id == lecturer_id,
    ))
    if sample is None:
        raise HTTPException(404, "Reference sample not found for this lecturer")
    return sample


def create_sample(db: Session, lecturer: Lecturer, upload: UploadFile,
                  label: str | None, storage: ReferenceStorage) -> VoiceSampleRead:
    stored = storage.prepare(upload)
    commit_started = False
    file_id = None
    try:
        file = AudioFile(
            file_role=FileRole.REFERENCE, recording_id=None, storage_path=stored.relative_path,
            original_filename=stored.original_filename, mime_type=stored.mime_type,
            file_size_bytes=stored.size, duration_seconds=stored.duration,
            sample_rate_hz=stored.sample_rate, channels=stored.channels,
        )
        sample = VoiceSample(lecturer=lecturer, audio_file=file, label=label or None)
        db.add(sample)
        db.flush()
        file_id = file.id
        response = sample_read(sample)
        commit_started = True
        db.commit()  # Includes deferred reference/voice-sample ownership checks.
        return response
    except Exception as exc:
        # A lost connection during COMMIT can have an unknown outcome. Never
        # delete bytes if committed metadata may still reference them.
        cleanup_safe = not commit_started or isinstance(exc, IntegrityError)
        try:
            db.rollback()
            if not cleanup_safe:
                cleanup_safe = db.scalar(select(AudioFile.id).where(AudioFile.id == file_id)) is None
        except Exception:
            logger.warning("Could not reconcile failed reference transaction for %s", stored.relative_path)
        if cleanup_safe:
            storage.cleanup(stored.relative_path)
        else:
            logger.warning("Reference retained after uncertain commit: %s", stored.relative_path)
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "Reference sample could not be saved because related data changed") from None
        raise


def delete_sample(db: Session, sample: VoiceSample, storage: ReferenceStorage) -> VoiceSampleDeleted:
    relative_path = sample.audio_file.storage_path
    storage.path(relative_path)  # Reject invalid persisted paths before modifying metadata.
    response = VoiceSampleDeleted(id=sample.id)
    file = sample.audio_file
    db.delete(sample)
    try:
        db.flush()  # Remove the referencing row before deleting the audio metadata.
        db.delete(file)
        commit_change(db, "Reference sample could not be deleted because related data changed")
    except Exception:
        db.rollback()
        raise
    # Keep the physical file until DB commit succeeds; failed unlinks are recoverable.
    response.file_cleanup_pending = not storage.cleanup(relative_path)
    return response

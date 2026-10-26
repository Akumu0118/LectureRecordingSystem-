import logging
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import AudioFile, FileRole, Recording, RecordingStatus
from app.schemas.lecturer import LecturerRead
from app.schemas.recording import RecordingDeleted, RecordingRead
from app.schemas.voice_sample import ReferenceAudioRead
from app.services.lecturers import commit_change
from app.services.recording_storage import RecordingStorage

logger = logging.getLogger(__name__)
RECORDING_LOAD = (joinedload(Recording.lecturer), selectinload(Recording.audio_files))


def require_recording(db: Session, recording_id: UUID, lock=False) -> Recording:
    query = select(Recording).options(*RECORDING_LOAD).where(Recording.id == recording_id)
    if lock:
        query = query.with_for_update(nowait=True, of=Recording)
    try:
        value = db.scalar(query)
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "55P03":
            raise HTTPException(409, "Recording is being uploaded or modified; refresh before retrying") from None
        raise
    if value is None:
        raise HTTPException(404, "Recording not found")
    return value


def original_file(value: Recording):
    return next((file for file in value.audio_files if file.file_role is FileRole.ORIGINAL), None)


def recording_read(value: Recording) -> RecordingRead:
    original = original_file(value)
    return RecordingRead(
        id=value.id, lecturer_id=value.lecturer_id, lecturer=LecturerRead.model_validate(value.lecturer),
        title=value.title, description=value.description, status=value.status,
        recorded_at=value.recorded_at, created_at=value.created_at, updated_at=value.updated_at,
        original_audio=ReferenceAudioRead.model_validate(original) if original else None,
        audio_url=f"/api/recordings/{value.id}/stream" if original else None,
    )


def mark_failed(db: Session, recording_id: UUID):
    try:
        value = require_recording(db, recording_id, lock=True)
        if value.status in {RecordingStatus.PENDING, RecordingStatus.FAILED} and original_file(value) is None:
            value.status = RecordingStatus.FAILED
            db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not mark failed upload for recording %s; retry is safe after reconciliation", recording_id)


def upload_original(db: Session, recording_id: UUID, upload: UploadFile,
                    storage: RecordingStorage) -> RecordingRead:
    value = require_recording(db, recording_id, lock=True)
    if original_file(value) is not None or value.status not in {RecordingStatus.PENDING, RecordingStatus.FAILED}:
        raise HTTPException(409, "Recording already has original audio or is not in an uploadable state")
    stored, file_id, committing = None, None, False
    try:
        # The row lock spans validation and commit. Concurrent writers fail fast.
        # UPLOADING is transaction-local; a crash rolls back to pending/failed.
        value.status = RecordingStatus.UPLOADING
        db.flush()
        stored = storage.prepare(upload)
        file = AudioFile(
            recording=value, file_role=FileRole.ORIGINAL, storage_path=stored.relative_path,
            original_filename=stored.original_filename, mime_type=stored.mime_type,
            file_size_bytes=stored.size, duration_seconds=stored.duration,
            sample_rate_hz=stored.sample_rate, channels=stored.channels,
        )
        db.add(file)
        value.status = RecordingStatus.READY
        db.flush()
        file_id = file.id
        response = recording_read(value)
        committing = True
        db.commit()
        return response
    except Exception as exc:
        cleanup_safe = not committing or isinstance(exc, IntegrityError)
        try:
            db.rollback()
            if not cleanup_safe:
                cleanup_safe = db.scalar(select(AudioFile.id).where(AudioFile.id == file_id)) is None
        except Exception:
            logger.warning("Recording commit outcome could not be reconciled: %s", recording_id)
        if stored:
            if cleanup_safe:
                storage.cleanup(stored.relative_path)
            else:
                logger.warning("Original file retained after uncertain commit: %s", stored.relative_path)
        if cleanup_safe:
            mark_failed(db, recording_id)
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "Original audio could not be saved because related data changed") from None
        raise


def delete_recording(db: Session, value: Recording, storage: RecordingStorage) -> RecordingDeleted:
    paths = [file.storage_path for file in value.audio_files]
    for path in paths:
        storage.path(path)
    response = RecordingDeleted(id=value.id)
    for file in list(value.audio_files):
        db.delete(file)
    try:
        db.flush()
        db.delete(value)
        commit_change(db, "Recording could not be deleted because related data changed")
    except Exception:
        db.rollback()
        raise
    for path in paths:
        # Keep any file which another metadata row references after our commit.
        try:
            referenced = db.scalar(select(AudioFile.id).where(AudioFile.storage_path == path)) is not None
        except Exception:
            referenced = True
            db.rollback()
        if referenced or not storage.cleanup(path):
            response.file_cleanup_pending = True
            logger.warning("Recording file cleanup pending for %s", path)
    return response

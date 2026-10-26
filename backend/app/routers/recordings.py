from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import FileRole, Recording, RecordingStatus
from app.schemas.audio_version import AudioVersion, AudioVersions
from app.schemas.recording import RecordingCreate, RecordingDeleted, RecordingPage, RecordingRead, RecordingUpdate
from app.services.audio_jobs import generate, version_read
from app.services.lecturers import commit_change, require_lecturer
from app.services.recording_storage import RecordingStorage, get_recording_storage
from app.services.recordings import RECORDING_LOAD, delete_recording, original_file, recording_read, require_recording, upload_original

router = APIRouter(prefix="/api/recordings", tags=["Lecture recordings"])
Database = Annotated[Session, Depends(get_db)]
Storage = Annotated[RecordingStorage, Depends(get_recording_storage)]


def matching_retry(existing: Recording, payload: RecordingCreate):
    return all(getattr(existing, name) == getattr(payload, name)
               for name in ("lecturer_id", "title", "description", "recorded_at"))


@router.post("", response_model=RecordingRead, status_code=201)
def create_recording(payload: RecordingCreate, response: Response, db: Database):
    require_lecturer(db, payload.lecturer_id)
    if payload.id is not None:
        existing = db.get(Recording, payload.id)
        if existing is not None:
            if not matching_retry(existing, payload):
                raise HTTPException(409, "Recording identifier is already in use with different metadata")
            response.status_code = 200
            return recording_read(existing)
    value = Recording(**payload.model_dump(exclude_none=True))
    db.add(value)
    try:
        db.flush()
        result = recording_read(value)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        if payload.id:
            existing = db.get(Recording, payload.id)
            if existing and matching_retry(existing, payload):
                response.status_code = 200
                return recording_read(existing)
        raise HTTPException(409, "Recording metadata could not be created because related data changed") from None
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=RecordingPage)
def list_recordings(db: Database, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                    offset: Annotated[int, Query(ge=0)] = 0,
                    q: Annotated[str | None, Query(max_length=200)] = None,
                    lecturer_id: UUID | None = None, status: RecordingStatus | None = None):
    conditions = []
    if lecturer_id is not None:
        conditions.append(Recording.lecturer_id == lecturer_id)
    if status is not None:
        conditions.append(Recording.status == status)
    if q and q.strip():
        # Search literal user text; '%' and '_' are not wildcard controls.
        pattern = '%' + q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        conditions.append(or_(Recording.title.ilike(pattern, escape='\\'), Recording.description.ilike(pattern, escape='\\')))
    total = db.scalar(select(func.count()).select_from(Recording).where(*conditions))
    rows = db.scalars(select(Recording).options(*RECORDING_LOAD).where(*conditions)
        .order_by(Recording.created_at.desc(), Recording.id).limit(limit).offset(offset)).all()
    return RecordingPage(items=[recording_read(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/{recording_id}", response_model=RecordingRead)
def get_recording(recording_id: UUID, db: Database):
    return recording_read(require_recording(db, recording_id))


@router.patch("/{recording_id}", response_model=RecordingRead)
def update_recording(recording_id: UUID, payload: RecordingUpdate, db: Database):
    value = require_recording(db, recording_id, lock=True)
    for name, field in payload.model_dump(exclude_unset=True).items():
        setattr(value, name, field)
    try:
        db.flush()
        db.refresh(value)
        result = recording_read(value)
        commit_change(db, "Recording could not be updated")
        return result
    except Exception:
        db.rollback()
        raise


@router.post("/{recording_id}/audio", response_model=RecordingRead)
def upload_recording(recording_id: UUID, db: Database, storage: Storage,
                     file: Annotated[UploadFile, File()]):
    return upload_original(db, recording_id, file, storage)


@router.get("/{recording_id}/stream", response_class=FileResponse)
def stream_recording(recording_id: UUID, db: Database, storage: Storage):
    value = require_recording(db, recording_id)
    file = original_file(value)
    if value.status is not RecordingStatus.READY or file is None:
        raise HTTPException(409, "Recording has no ready original audio")
    path = storage.path(file.storage_path)
    if not path.is_file():
        raise HTTPException(404, "Original lecture audio file is missing")
    return FileResponse(path, media_type=file.mime_type, filename=f"lecture-{value.id}{path.suffix}",
                        content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{recording_id}", response_model=RecordingDeleted)
def remove_recording(recording_id: UUID, db: Database, storage: Storage):
    return delete_recording(db, require_recording(db, recording_id, lock=True), storage)

# Derived audio stays scoped to its owning recording. No public storage mount.


@router.post("/{recording_id}/exports", response_model=AudioVersion)
def export_mp3(recording_id: UUID, response: Response, db: Database, storage: Storage):
    result, created = generate(db, recording_id, FileRole.EXPORTED, storage)
    response.status_code = 201 if created else 200
    return result


@router.get("/{recording_id}/exports", response_model=AudioVersions)
def list_exports(recording_id: UUID, db: Database, storage: Storage):
    value = require_recording(db, recording_id)
    return AudioVersions(items=[version_read(value.id, file, storage) for file in value.audio_files
                                if file.file_role is FileRole.EXPORTED])


@router.post("/{recording_id}/process", response_model=AudioVersion)
def process_audio(recording_id: UUID, response: Response, db: Database, storage: Storage):
    result, created = generate(db, recording_id, FileRole.PROCESSED, storage)
    response.status_code = 201 if created else 200
    return result


@router.get("/{recording_id}/versions", response_model=AudioVersions)
def list_versions(recording_id: UUID, db: Database, storage: Storage):
    value = require_recording(db, recording_id)
    return AudioVersions(items=[version_read(value.id, file, storage) for file in
                                sorted(value.audio_files, key=lambda file: (file.created_at, str(file.id)))])


def version_response(recording_id, file_id, db, storage, disposition):
    value = require_recording(db, recording_id)
    file = next((file for file in value.audio_files if file.id == file_id), None)
    if file is None:
        raise HTTPException(404, "Audio version not found for this recording")
    path = storage.path(file.storage_path)
    if not path.is_file():
        raise HTTPException(404, "Stored audio version is missing")
    # UUID-only download names keep response headers independent of user text.
    return FileResponse(path, media_type=file.mime_type, filename=f"lecture-{value.id}-{file.file_role.value}{path.suffix}",
                        content_disposition_type=disposition, headers={"X-Content-Type-Options": "nosniff"})


@router.get("/{recording_id}/versions/{file_id}/audio", response_class=FileResponse)
def play_version(recording_id: UUID, file_id: UUID, db: Database, storage: Storage):
    return version_response(recording_id, file_id, db, storage, "inline")


@router.get("/{recording_id}/versions/{file_id}/download", response_class=FileResponse)
def download_version(recording_id: UUID, file_id: UUID, db: Database, storage: Storage):
    return version_response(recording_id, file_id, db, storage, "attachment")

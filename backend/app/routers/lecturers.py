from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import Lecturer, VoiceSample
from app.schemas.lecturer import LecturerCreate, LecturerPage, LecturerRead, LecturerUpdate, OptionalText
from app.schemas.voice_sample import VoiceSampleDeleted, VoiceSamplePage, VoiceSampleRead
from app.services.lecturers import commit_change, require_lecturer
from app.services.reference_storage import ReferenceStorage, get_reference_storage
from app.services.voice_samples import create_sample, delete_sample, require_sample, sample_read

router = APIRouter(prefix="/api/lecturers", tags=["Lecturers and reference samples"])
Database = Annotated[Session, Depends(get_db)]
Storage = Annotated[ReferenceStorage, Depends(get_reference_storage)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("", response_model=LecturerRead, status_code=201)
def register_lecturer(payload: LecturerCreate, db: Database):
    value = Lecturer(**payload.model_dump())
    db.add(value)
    try:
        db.flush()
        response = LecturerRead.model_validate(value)
        commit_change(db, "Lecturer could not be created")
        return response
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=LecturerPage)
def list_lecturers(db: Database, limit: Limit = 20, offset: Offset = 0):
    total = db.scalar(select(func.count()).select_from(Lecturer))
    items = db.scalars(select(Lecturer).order_by(Lecturer.created_at.desc(), Lecturer.id)
                       .limit(limit).offset(offset)).all()
    return LecturerPage(items=[LecturerRead.model_validate(item) for item in items],
                        total=total, limit=limit, offset=offset)


@router.get("/{lecturer_id}", response_model=LecturerRead)
def get_lecturer(lecturer_id: UUID, db: Database):
    return require_lecturer(db, lecturer_id)


@router.patch("/{lecturer_id}", response_model=LecturerRead)
def update_lecturer(lecturer_id: UUID, payload: LecturerUpdate, db: Database):
    value = require_lecturer(db, lecturer_id)
    for key, field in payload.model_dump(exclude_unset=True).items():
        setattr(value, key, field)
    try:
        db.flush()
        db.refresh(value)
        response = LecturerRead.model_validate(value)
        commit_change(db, "Lecturer could not be updated")
        return response
    except Exception:
        db.rollback()
        raise


@router.delete("/{lecturer_id}", status_code=204)
def remove_lecturer(lecturer_id: UUID, db: Database):
    value = require_lecturer(db, lecturer_id)
    db.delete(value)
    commit_change(db, "Lecturer has recordings or reference samples; remove those relationships before deleting")
    return Response(status_code=204)


@router.post("/{lecturer_id}/samples", response_model=VoiceSampleRead, status_code=201)
def upload_reference(lecturer_id: UUID, db: Database, storage: Storage,
                     file: Annotated[UploadFile, File()],
                     label: Annotated[OptionalText | None, Form()] = None):
    """Upload one audio-only WAV/MP3/WebM reference; optional label is form data."""
    return create_sample(db, require_lecturer(db, lecturer_id), file, label, storage)


@router.get("/{lecturer_id}/samples", response_model=VoiceSamplePage)
def list_samples(lecturer_id: UUID, db: Database, limit: Limit = 20, offset: Offset = 0):
    require_lecturer(db, lecturer_id)
    total = db.scalar(select(func.count()).select_from(VoiceSample).where(VoiceSample.lecturer_id == lecturer_id))
    samples = db.scalars(select(VoiceSample).options(joinedload(VoiceSample.audio_file))
        .where(VoiceSample.lecturer_id == lecturer_id)
        .order_by(VoiceSample.created_at.desc(), VoiceSample.id).limit(limit).offset(offset)).all()
    return VoiceSamplePage(items=[sample_read(value) for value in samples], total=total, limit=limit, offset=offset)


@router.get("/{lecturer_id}/samples/{sample_id}", response_model=VoiceSampleRead)
def get_sample(lecturer_id: UUID, sample_id: UUID, db: Database):
    require_lecturer(db, lecturer_id)
    return sample_read(require_sample(db, lecturer_id, sample_id))


@router.get("/{lecturer_id}/samples/{sample_id}/audio", response_class=FileResponse)
def play_sample(lecturer_id: UUID, sample_id: UUID, db: Database, storage: Storage):
    """Serve a lecturer-scoped reference with HTTP byte-range support."""
    require_lecturer(db, lecturer_id)
    sample = require_sample(db, lecturer_id, sample_id)
    path = storage.path(sample.audio_file.storage_path)
    if not path.is_file():
        raise HTTPException(404, "Reference audio file is missing")
    return FileResponse(path, media_type=sample.audio_file.mime_type,
                        filename=f"reference-{sample.id}{path.suffix}",
                        content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{lecturer_id}/samples/{sample_id}", response_model=VoiceSampleDeleted)
def remove_sample(lecturer_id: UUID, sample_id: UUID, db: Database, storage: Storage):
    require_lecturer(db, lecturer_id)
    return delete_sample(db, require_sample(db, lecturer_id, sample_id), storage)

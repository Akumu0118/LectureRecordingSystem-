from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import FileRole


class ReferenceAudioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    file_role: FileRole
    original_filename: str | None
    mime_type: str
    file_size_bytes: int
    duration_seconds: Decimal | None
    sample_rate_hz: int | None
    channels: int | None
    created_at: datetime


class VoiceSampleRead(BaseModel):
    id: UUID
    lecturer_id: UUID
    label: str | None
    created_at: datetime
    audio_file: ReferenceAudioRead
    audio_url: str


class VoiceSamplePage(BaseModel):
    items: list[VoiceSampleRead]
    total: int
    limit: int
    offset: int


class VoiceSampleDeleted(BaseModel):
    id: UUID
    deleted: bool = True
    file_cleanup_pending: bool = False

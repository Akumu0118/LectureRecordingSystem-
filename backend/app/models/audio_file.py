from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.recording import Recording
    from app.models.voice_sample import VoiceSample


class FileRole(str, Enum):
    REFERENCE = "reference"
    ORIGINAL = "original"
    EXPORTED = "exported"
    PROCESSED = "processed"


class AudioFile(Base):
    __tablename__ = "audio_files"
    __table_args__ = (
        UniqueConstraint("storage_path", name="uq_audio_files_storage_path"),
        CheckConstraint("file_size_bytes >= 0", name="ck_audio_files_size_nonnegative"),
        CheckConstraint("duration_seconds >= 0 AND duration_seconds <> 'NaN'::numeric", name="ck_audio_files_duration_nonnegative"),
        CheckConstraint("sample_rate_hz > 0", name="ck_audio_files_sample_rate_positive"),
        CheckConstraint("channels > 0", name="ck_audio_files_channels_positive"),
        CheckConstraint("btrim(storage_path) <> ''", name="ck_audio_files_storage_path_nonempty"),
        CheckConstraint("btrim(mime_type) <> ''", name="ck_audio_files_mime_type_nonempty"),
        CheckConstraint(
            "(file_role = 'reference' AND recording_id IS NULL) OR "
            "(file_role IN ('original', 'exported', 'processed') AND recording_id IS NOT NULL)",
            name="ck_audio_files_role_recording",
        ),
        Index("ix_audio_files_recording_role", "recording_id", "file_role"),
        Index("ix_audio_files_created_at", "created_at"),
        Index("uq_audio_files_original_recording", "recording_id", unique=True,
              postgresql_where=text("file_role = 'original'")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    recording_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("recordings.id", name="fk_audio_files_recording_id", ondelete="RESTRICT"))
    file_role: Mapped[FileRole] = mapped_column(
        SAEnum(FileRole, values_callable=lambda cls: [item.value for item in cls], native_enum=False, create_constraint=True, name="ck_audio_files_file_role", length=16)
    )
    storage_path: Mapped[str] = mapped_column(String(1024))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(127))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    sample_rate_hz: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recording: Mapped[Recording | None] = relationship(back_populates="audio_files")
    voice_sample: Mapped[VoiceSample | None] = relationship(back_populates="audio_file", passive_deletes="all")

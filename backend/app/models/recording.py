from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, FetchedValue, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.audio_file import AudioFile
    from app.models.lecturer import Lecturer


class RecordingStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    READY = "ready"
    FAILED = "failed"


class Recording(Base):
    __tablename__ = "recordings"
    __table_args__ = (
        CheckConstraint("btrim(title) <> ''", name="ck_recordings_title_nonempty"),
        Index("ix_recordings_lecturer_created_at", "lecturer_id", "created_at"),
        Index("ix_recordings_created_at", "created_at"),
        Index("ix_recordings_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    lecturer_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("lecturers.id", name="fk_recordings_lecturer_id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RecordingStatus] = mapped_column(
        SAEnum(RecordingStatus, values_callable=lambda cls: [item.value for item in cls], native_enum=False, create_constraint=True, name="ck_recordings_status", length=16),
        default=RecordingStatus.PENDING, server_default=text("'pending'"),
    )
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), server_onupdate=FetchedValue())

    lecturer: Mapped[Lecturer] = relationship(back_populates="recordings")
    audio_files: Mapped[list[AudioFile]] = relationship(back_populates="recording", passive_deletes="all")

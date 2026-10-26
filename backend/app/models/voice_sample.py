from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.audio_file import AudioFile
    from app.models.lecturer import Lecturer


class VoiceSample(Base):
    __tablename__ = "voice_samples"
    __table_args__ = (
        UniqueConstraint("audio_file_id", name="uq_voice_samples_audio_file_id"),
        Index("ix_voice_samples_lecturer_created_at", "lecturer_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    lecturer_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("lecturers.id", name="fk_voice_samples_lecturer_id", ondelete="RESTRICT"))
    audio_file_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("audio_files.id", name="fk_voice_samples_audio_file_id", ondelete="RESTRICT"))
    label: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lecturer: Mapped[Lecturer] = relationship(back_populates="voice_samples")
    audio_file: Mapped[AudioFile] = relationship(back_populates="voice_sample")

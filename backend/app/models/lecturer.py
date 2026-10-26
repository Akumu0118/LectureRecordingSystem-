from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, FetchedValue, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.recording import Recording
    from app.models.voice_sample import VoiceSample


class Lecturer(Base):
    __tablename__ = "lecturers"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_lecturers_name_nonempty"),
        Index("ix_lecturers_name", "name"),
        Index("ix_lecturers_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), server_onupdate=FetchedValue())

    voice_samples: Mapped[list[VoiceSample]] = relationship(back_populates="lecturer", passive_deletes="all")
    recordings: Mapped[list[Recording]] = relationship(back_populates="lecturer", passive_deletes="all")

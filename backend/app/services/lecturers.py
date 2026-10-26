from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Lecturer


def require_lecturer(db: Session, lecturer_id: UUID) -> Lecturer:
    lecturer = db.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(404, "Lecturer not found")
    return lecturer


def commit_change(db: Session, conflict_message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, conflict_message) from None
    except Exception:
        db.rollback()
        raise

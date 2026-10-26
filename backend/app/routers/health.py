from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    responses={503: {"description": "Database not configured or unavailable"}},
)
def database_health(db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    db.execute(text("SELECT 1"))
    return DatabaseHealthResponse()

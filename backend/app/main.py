from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import DatabaseNotConfigured, get_engine
from app.core.upload_limits import ReferenceUploadLimit
from app.routers.health import router as health_router
from app.routers.lecturers import router as lecturers_router
from app.routers.recordings import router as recordings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()


app = FastAPI(title="VoiceClean API", version="0.1.0", lifespan=lifespan)
app.add_middleware(ReferenceUploadLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Range"],
    expose_headers=["Accept-Ranges", "Content-Range"],
)


@app.exception_handler(DatabaseNotConfigured)
async def database_not_configured(request: Request, exc: DatabaseNotConfigured):
    return JSONResponse(status_code=503, content={"detail": "Database is not configured"})


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request: Request, exc: SQLAlchemyError):
    # Do not return driver errors, connection strings, or credentials to clients.
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable"})


app.include_router(health_router)
app.include_router(lecturers_router)
app.include_router(recordings_router)

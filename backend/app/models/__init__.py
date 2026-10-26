"""Register all application models with SQLAlchemy and Alembic."""

from app.models.audio_file import AudioFile, FileRole
from app.models.lecturer import Lecturer
from app.models.recording import Recording, RecordingStatus
from app.models.voice_sample import VoiceSample

__all__ = ["AudioFile", "FileRole", "Lecturer", "Recording", "RecordingStatus", "VoiceSample"]

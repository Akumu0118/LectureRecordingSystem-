from contextlib import contextmanager
from io import BytesIO
import math
from pathlib import Path
import shutil
import struct
import subprocess
from types import SimpleNamespace
from uuid import uuid4
import wave

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core import upload_limits
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import AudioFile, FileRole
from app.services.reference_storage import ReferenceStorage, get_reference_storage
from app.services.recording_storage import RecordingStorage, get_recording_storage


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def isolated_database():
    url = get_settings().database_url
    if url is None:
        pytest.skip("Real PostgreSQL tests require local DATABASE_URL")
    engine = create_engine(url.get_secret_value(), connect_args={"connect_timeout": 5})
    schema = "voiceclean_test_" + uuid4().hex
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET search_path TO "{schema}", public'))
            connection.execute(text("CREATE TABLE unrelated_test_sentinel (id integer PRIMARY KEY)"))
            connection.execute(text("INSERT INTO unrelated_test_sentinel VALUES (1)"))
            connection.commit()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
            command.check(config)
            connection.commit()
            # Test reversibility only here, never in the application schema.
            command.downgrade(config, "base")
            connection.commit()
            assert not ({"lecturers", "recordings", "voice_samples", "audio_files"}
                        & set(inspect(connection).get_table_names(schema=schema)))
            assert connection.execute(text("SELECT id FROM unrelated_test_sentinel")).scalar_one() == 1
            connection.commit()
            command.upgrade(config, "head")
            connection.commit()
            command.check(config)
            connection.commit()
            yield engine, schema
    finally:
        # Validate the generated identifier before cleanup. Never drop public.
        assert schema.startswith("voiceclean_test_") and len(schema) == 48
        with engine.begin() as cleanup:
            cleanup.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()



@pytest.fixture(scope="session")
def audio_assets(tmp_path_factory):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.fail("Audio integration tests require FFmpeg and FFprobe on PATH")
    target = tmp_path_factory.mktemp("voiceclean_audio")
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(b"".join(struct.pack("<h", int(10000 * math.sin(2 * math.pi * 440 * n / 16000))) for n in range(4000)))
    source = target / "tone.wav"
    source.write_bytes(buffer.getvalue())
    mp3 = subprocess.run([ffmpeg, "-v", "error", "-i", str(source), "-f", "mp3", "pipe:1"], capture_output=True, check=True, timeout=20).stdout
    # Non-seekable output simulates MediaRecorder WebM without a duration header.
    webm = subprocess.run([ffmpeg, "-v", "error", "-i", str(source), "-c:a", "libopus", "-f", "webm", "pipe:1"], capture_output=True, check=True, timeout=20).stdout
    video = subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:duration=0.25",
        "-an", "-c:v", "libvpx-vp9", "-f", "webm", "pipe:1"], capture_output=True, check=True, timeout=20).stdout
    return {"wav": buffer.getvalue(), "mp3": mp3, "webm": webm, "video": video, "ffprobe": ffprobe}


@pytest.fixture
def api(isolated_database, tmp_path, monkeypatch, audio_assets):
    engine, schema = isolated_database
    settings = get_settings().model_copy(update={"storage_root": tmp_path, "ffprobe_path": audio_assets["ffprobe"]})
    storage = ReferenceStorage(settings)
    recording_storage = RecordingStorage(settings)
    state = SimpleNamespace(client=None, storage=storage, recording_storage=recording_storage, settings=settings, schema=schema,
                            fail_commit=False, corrupt_commit=False, ambiguous_commit=False)

    @contextmanager
    def session_scope():
        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema}", public'))
            connection.commit()
            with Session(bind=connection) as session:
                if state.fail_commit:
                    def unavailable():
                        raise OperationalError("private connection details", {}, Exception("private"))
                    session.commit = unavailable
                if state.corrupt_commit:
                    @event.listens_for(session, "before_commit")
                    def invalid_owner(db):
                        db.add(AudioFile(file_role=FileRole.REFERENCE, storage_path=f"references/{uuid4()}.wav",
                                         mime_type="audio/wav", file_size_bytes=1))
                if state.ambiguous_commit:
                    real_commit = session.commit
                    def lost_acknowledgment():
                        real_commit()
                        raise OperationalError("private", {}, Exception("lost commit acknowledgment"))
                    session.commit = lost_acknowledgment
                yield session

    def override_db():
        with session_scope() as session:
            yield session

    state.session = session_scope
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_reference_storage] = lambda: storage
    app.dependency_overrides[get_recording_storage] = lambda: recording_storage
    monkeypatch.setattr(upload_limits, "get_settings", lambda: settings)
    try:
        with TestClient(app) as client:
            state.client = client
            yield state
    finally:
        app.dependency_overrides.clear()


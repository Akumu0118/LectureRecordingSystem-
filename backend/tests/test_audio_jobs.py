"""Real FFmpeg/PostgreSQL/filesystem tests; all data belongs to the private fixture."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4
import subprocess

import pytest

from app.models import AudioFile, FileRole
from app.services import audio_jobs
from tests.test_recording_api import create, attach


def ready(api, assets, kind="wav"):
    identifier = create(api).json()["id"]
    assert attach(api, identifier, assets, kind).status_code == 200
    return identifier


def url(identifier, action="exports"):
    return f"/api/recordings/{identifier}/{action}"


@pytest.mark.parametrize("kind", ["wav", "mp3", "webm"])
@pytest.mark.parametrize("action,role,mime,rate", [
    ("exports", "exported", "audio/mpeg", 32000), ("process", "processed", "audio/wav", 16000)])
def test_real_generation_metadata_reuse_and_scoped_playback(api, audio_assets, kind, action, role, mime, rate):
    identifier = ready(api, audio_assets, kind)
    original = api.client.get(f"/api/recordings/{identifier}").json()
    response = api.client.post(url(identifier, action))
    assert response.status_code == 201, response.text
    version = response.json()
    assert version["file_role"] == role
    assert version["mime_type"] == mime
    assert version["sample_rate_hz"] == rate and version["channels"] == 1
    assert version["available"] and version["preset"]
    assert "storage_path" not in version and "storage_root" not in response.text
    playback = api.client.get(version["audio_url"])
    assert playback.status_code == 200
    assert len(playback.content) == version["file_size_bytes"]
    assert playback.headers["content-type"] == mime
    assert api.client.get(version["audio_url"], headers={"Range": "bytes=0-9"}).status_code == 206
    download = api.client.get(version["download_url"])
    assert download.content == playback.content
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["x-content-type-options"] == "nosniff"
    retry = api.client.post(url(identifier, action))
    assert retry.status_code == 200 and retry.json()["id"] == version["id"]
    assert api.client.get(original["audio_url"]).content == audio_assets[kind]
    versions = api.client.get(url(identifier, "versions")).json()["items"]
    assert {file["file_role"] for file in versions} == {"original", role}
    exports = api.client.get(url(identifier)).json()["items"]
    assert len(exports) == (1 if action == "exports" else 0)
    with api.session() as db:
        file = db.get(AudioFile, version["id"])
        assert file.recording_id == UUID(identifier)
        assert file.storage_path.startswith("exports/" if role == "exported" else "processed/")
        assert len(list(api.settings.storage_root.glob(file.storage_path))) == 1


def test_missing_and_pending_recordings_and_cross_recording_access(api, audio_assets):
    assert api.client.post(url(uuid4())).status_code == 404
    pending = create(api).json()["id"]
    for action in ["exports", "process"]:
        assert api.client.post(url(pending, action)).status_code == 409
    identifier = ready(api, audio_assets)
    version = api.client.post(url(identifier)).json()
    for suffix in ["audio", "download"]:
        assert api.client.get(f"/api/recordings/{pending}/versions/{version['id']}/{suffix}").status_code == 404
    assert api.client.get(url(identifier, "versions/bad/download")).status_code == 422


@pytest.mark.parametrize("failure", ["missing", "invalid"])
def test_original_failure_does_not_generate_or_mutate(api, audio_assets, failure):
    identifier = ready(api, audio_assets)
    original = next(api.settings.storage_root.glob("recordings/*"))
    if failure == "missing":
        original.unlink()
    else:
        original.write_bytes(b"not audio")
    result = api.client.post(url(identifier))
    assert result.status_code == (404 if failure == "missing" else 422)
    assert not list(api.settings.storage_root.glob("exports/*"))
    assert api.client.get(f"/api/recordings/{identifier}").json()["status"] == "ready"


@pytest.mark.parametrize("failure,expected", [("ffmpeg",503), ("ffprobe",503), ("timeout",504), ("execution",422), ("disk",503), ("output",413)])
def test_job_failures_leave_original_and_no_metadata_or_files(api, audio_assets, monkeypatch, failure, expected):
    identifier = ready(api, audio_assets)
    if failure in {"ffmpeg", "ffprobe"}:
        monkeypatch.setattr(api.settings, failure + "_path", "nonexistent-voiceclean-tool.exe")
    elif failure == "output":
        monkeypatch.setattr(api.settings, "max_generated_size_bytes", 100)
    else:
        actual_run = audio_jobs.subprocess.run
        def fail(command, **kwargs):
            if "-nostdin" not in command:
                return actual_run(command, **kwargs)
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, 0.001)
            if failure == "disk":
                raise OSError("private path / disk full")
            return subprocess.CompletedProcess(command, 1)
        monkeypatch.setattr(audio_jobs.subprocess, "run", fail)
    result = api.client.post(url(identifier))
    assert result.status_code == expected, result.text
    assert "private" not in result.text
    assert api.client.get(f"/api/recordings/{identifier}/stream").content == audio_assets["wav"]
    assert not list(api.settings.storage_root.glob("exports/*"))
    assert len(api.client.get(url(identifier, "versions")).json()["items"]) == 1


@pytest.mark.parametrize("action", ["exports", "process"])
@pytest.mark.parametrize("failure", ["fail_commit", "corrupt_commit", "ambiguous_commit"])
def test_transaction_rollback_and_uncertain_commit(api, audio_assets, action, failure):
    identifier = ready(api, audio_assets)
    setattr(api, failure, True)
    result = api.client.post(url(identifier, action))
    setattr(api, failure, False)
    assert result.status_code == (409 if failure == "corrupt_commit" else 503), result.text
    files = list(api.settings.storage_root.glob(("exports" if action == "exports" else "processed") + "/*"))
    versions = api.client.get(url(identifier, "versions")).json()["items"]
    if failure == "ambiguous_commit":
        assert len(files) == 1 and len(versions) == 2
        assert api.client.post(url(identifier, action)).status_code == 200
    else:
        assert not files and len(versions) == 1
    assert api.client.get(f"/api/recordings/{identifier}/stream").content == audio_assets["wav"]


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_missing_or_corrupt_derivative_regenerated_without_changing_original(api, audio_assets, damage):
    identifier = ready(api, audio_assets)
    first = api.client.post(url(identifier)).json()
    file = next(api.settings.storage_root.glob("exports/*"))
    if damage == "missing":
        file.unlink()
    else:
        file.write_bytes(b"invalid")
    assert api.client.get(url(identifier, "versions")).status_code == 200
    new = api.client.post(url(identifier))
    assert new.status_code == 201 and new.json()["id"] != first["id"]
    assert len(list(api.settings.storage_root.glob("exports/*"))) == 1
    assert len(api.client.get(url(identifier)).json()["items"]) == 1


def test_concurrent_job_blocks_same_recording_but_not_unrelated_requests(api, audio_assets, monkeypatch):
    identifier = ready(api, audio_assets)
    entered, release = Event(), Event()
    actual = audio_jobs.convert
    def slow(*args):
        entered.set()
        assert release.wait(10)
        return actual(*args)
    monkeypatch.setattr(audio_jobs, "convert", slow)
    with ThreadPoolExecutor() as executor:
        task = executor.submit(api.client.post, url(identifier))
        assert entered.wait(10)
        try:
            assert api.client.post(url(identifier)).status_code == 409
            assert api.client.post(url(identifier, "process")).status_code == 409
            assert api.client.delete(f"/api/recordings/{identifier}").status_code == 409
            assert api.client.patch(f"/api/recordings/{identifier}", json={"title":"Concurrent"}).status_code == 409
            assert api.client.get("/health").status_code == 200
            assert api.client.get(f"/api/recordings/{identifier}/stream").status_code == 200
        finally:
            release.set()
        assert task.result().status_code == 201


def test_global_job_limit_and_retry(api, audio_assets, monkeypatch):
    identifier = ready(api, audio_assets)
    slots = audio_jobs.job_slots(api.settings.max_audio_jobs)
    for _ in range(api.settings.max_audio_jobs):
        assert slots.acquire(blocking=False)
    try:
        assert api.client.post(url(identifier)).status_code == 503
    finally:
        for _ in range(api.settings.max_audio_jobs):
            slots.release()
    assert api.client.post(url(identifier)).status_code == 201


def test_delete_cleans_all_versions_and_failed_delete_retains_bytes(api, audio_assets):
    identifier = ready(api, audio_assets)
    generated = [api.client.post(url(identifier, action)).json() for action in ["exports", "process"]]
    api.fail_commit = True
    assert api.client.delete(f"/api/recordings/{identifier}").status_code == 503
    api.fail_commit = False
    for file in generated:
        assert api.client.get(file["download_url"]).status_code == 200
    assert api.client.delete(f"/api/recordings/{identifier}").json()["file_cleanup_pending"] is False
    assert not [file for file in api.settings.storage_root.rglob("*") if file.is_file()]

def test_generated_audio_is_independently_decodable(api, audio_assets):
    import json
    identifier = ready(api, audio_assets)
    for action, codec, rate in [("exports", "mp3", "32000"), ("process", "pcm_s16le", "16000")]:
        response = api.client.post(url(identifier, action)).json()
        with api.session() as db:
            path = api.recording_storage.path(db.get(AudioFile, response["id"]).storage_path)
        result = subprocess.run([audio_assets["ffprobe"], "-v", "error", "-show_streams", "-of", "json", str(path)],
                                capture_output=True, check=True, timeout=20)
        streams = json.loads(result.stdout)["streams"]
        assert len(streams) == 1
        assert streams[0]["codec_type"] == "audio" and streams[0]["codec_name"] == codec
        assert streams[0]["sample_rate"] == rate and streams[0]["channels"] == 1


def test_failed_rollback_file_cleanup_is_logged_and_never_breaks_original(api, audio_assets, monkeypatch, caplog):
    identifier = ready(api, audio_assets)
    from pathlib import Path
    real_unlink = Path.unlink
    def failure(path, *args, **kwargs):
        if path.parent.name == "exports" and not path.name.startswith(".job-"):
            raise PermissionError("test file is busy")
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", failure)
    api.fail_commit = True
    assert api.client.post(url(identifier)).status_code == 503
    api.fail_commit = False
    assert "cleanup pending" in caplog.text
    assert len(api.client.get(url(identifier, "versions")).json()["items"]) == 1
    assert api.client.get(f"/api/recordings/{identifier}/stream").content == audio_assets["wav"]
    leftover = next(api.settings.storage_root.glob("exports/*"))
    monkeypatch.setattr(Path, "unlink", real_unlink)
    assert api.recording_storage.cleanup("exports/" + leftover.name)


def test_derivative_cleanup_failure_after_delete_reports_pending(api, audio_assets, monkeypatch):
    identifier = ready(api, audio_assets)
    assert api.client.post(url(identifier, "process")).status_code == 201
    assert api.client.post(url(identifier)).status_code == 201
    monkeypatch.setattr(api.recording_storage, "cleanup", lambda path: False)
    response = api.client.delete(f"/api/recordings/{identifier}")
    assert response.status_code == 200 and response.json()["file_cleanup_pending"] is True
    assert api.client.get(url(identifier, "versions")).status_code == 404
    assert len([file for file in api.settings.storage_root.rglob("*") if file.is_file()]) == 3


def test_generated_output_probe_failure_cleans_staging_file(api, audio_assets, monkeypatch):
    from fastapi import HTTPException
    identifier = ready(api, audio_assets)
    probe = api.recording_storage.probe
    def reject_output(path, suffix):
        if path.name.startswith(".job-"):
            raise HTTPException(422, "Generated audio validation failed")
        return probe(path, suffix)
    monkeypatch.setattr(api.recording_storage, "probe", reject_output)
    assert api.client.post(url(identifier)).status_code == 422
    assert not list(api.settings.storage_root.glob("exports/*"))
    assert len(api.client.get(url(identifier, "versions")).json()["items"]) == 1


def test_conversion_disk_full_error_is_sanitized(api, audio_assets, monkeypatch):
    identifier = ready(api, audio_assets)
    run = audio_jobs.subprocess.run
    def full(command, **kwargs):
        if "-nostdin" not in command:
            return run(command, **kwargs)
        kwargs["stderr"].write(b"private/path: No space left on device")
        return subprocess.CompletedProcess(command, 1)
    monkeypatch.setattr(audio_jobs.subprocess, "run", full)
    result = api.client.post(url(identifier))
    assert result.status_code == 503 and "disk space" in result.json()["detail"]
    assert "private" not in result.text
    assert not list(api.settings.storage_root.glob("exports/*"))


def test_unsafe_persisted_paths_are_never_served_or_processed(api, audio_assets):
    identifier = ready(api, audio_assets)
    file_id = api.client.get(f"/api/recordings/{identifier}").json()["original_audio"]["id"]
    with api.session() as db:
        db.get(AudioFile, file_id).storage_path = "recordings/../../outside.wav"
        db.commit()
    assert api.client.get(url(identifier, f"versions/{file_id}/download")).status_code == 503
    assert api.client.post(url(identifier)).status_code == 503

def test_unreconciled_commit_retains_generated_file_for_recovery(api, audio_assets, monkeypatch, caplog):
    from sqlalchemy.exc import OperationalError
    identifier = ready(api, audio_assets)
    with api.session() as db:
        commit = db.commit
        def unavailable(*args, **kwargs):
            raise OperationalError("private", {}, Exception("private"))
        def lost_acknowledgment():
            commit()
            monkeypatch.setattr(db, "scalar", unavailable)
            unavailable()
        monkeypatch.setattr(db, "commit", lost_acknowledgment)
        with pytest.raises(OperationalError):
            audio_jobs.generate(db, UUID(identifier), FileRole.EXPORTED, api.recording_storage)
    assert "retained after uncertain commit" in caplog.text
    assert len(list(api.settings.storage_root.glob("exports/*"))) == 1
    assert len(api.client.get(url(identifier, "versions")).json()["items"]) == 2
    assert api.client.post(url(identifier)).status_code == 200

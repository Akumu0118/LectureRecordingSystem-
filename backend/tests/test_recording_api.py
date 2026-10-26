from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import AudioFile, FileRole
from tests.server_process import live_api
from tests.test_lecturer_api import register, upload as reference_upload


def create(api, owner=None, **values):
    payload = {"lecturer_id": owner or register(api), "title": "DSP Lecture", **values}
    return api.client.post("/api/recordings", json=payload)


def attach(api, value, assets, suffix="wav"):
    return api.client.post(f"/api/recordings/{value}/audio",
        files={"file": (f"lecture.{suffix}", assets[suffix], "application/octet-stream")})


def test_create_association_detail_and_idempotent_retry(api):
    owner = register(api)
    identifier = str(uuid4())
    payload = {"id": identifier, "lecturer_id": owner, "title": "  Signals  ", "recorded_at": "2026-10-26T09:00:00+08:00"}
    response = api.client.post("/api/recordings", json=payload)
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["title"] == "Signals"
    assert value["lecturer"]["id"] == owner
    assert value["status"] == "pending"
    assert value["original_audio"] is None
    assert api.client.get(f"/api/recordings/{identifier}").status_code == 200
    assert api.client.post("/api/recordings", json=payload).status_code == 200
    payload["title"] = "Different"
    assert api.client.post("/api/recordings", json=payload).status_code == 409


@pytest.mark.parametrize("fields", [{"title": " "}, {"title": None}, {"title": "x" * 251},
    {"description": "\u0000"}, {"recorded_at": "2026-10-26T09:00:00"}, {"status": "ready"}])
def test_create_validation(api, fields):
    assert create(api, **fields).status_code == 422


def test_missing_lecturer_and_recording(api, audio_assets):
    assert create(api, owner=str(uuid4())).status_code == 404
    identifier = str(uuid4())
    assert api.client.get(f"/api/recordings/{identifier}").status_code == 404
    assert attach(api, identifier, audio_assets).status_code == 404
    assert api.client.get(f"/api/recordings/{identifier}/stream").status_code == 404
    assert api.client.delete(f"/api/recordings/{identifier}").status_code == 404
    assert api.client.get("/api/recordings/not-a-uuid").status_code == 422


@pytest.mark.parametrize("suffix", ["wav", "mp3", "webm"])
def test_original_upload_metadata_playback_and_duplicate_protection(api, audio_assets, suffix):
    identifier = create(api).json()["id"]
    response = attach(api, identifier, audio_assets, suffix)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["status"] == "ready"
    assert value["original_audio"]["file_role"] == "original"
    assert value["original_audio"]["file_size_bytes"] == len(audio_assets[suffix])
    assert float(value["original_audio"]["duration_seconds"]) > 0
    stream = api.client.get(value["audio_url"])
    assert stream.status_code == 200
    assert stream.content == audio_assets[suffix]
    assert int(stream.headers["content-length"]) == len(audio_assets[suffix])
    partial = api.client.get(value["audio_url"], headers={"Range": "bytes=10-29"})
    assert partial.status_code == 206
    assert partial.content == audio_assets[suffix][10:30]
    assert partial.headers["content-range"] == f"bytes 10-29/{len(audio_assets[suffix])}"
    assert attach(api, identifier, audio_assets, suffix).status_code == 409
    with api.session() as db:
        file = db.get(AudioFile, value["original_audio"]["id"])
        assert file.storage_path.startswith("recordings/")
        assert api.recording_storage.path(file.storage_path).read_bytes() == audio_assets[suffix]
    assert len(list(api.settings.storage_root.glob("recordings/*"))) == 1


def test_database_unique_original_index(api, audio_assets):
    identifier = create(api).json()["id"]
    assert attach(api, identifier, audio_assets).status_code == 200
    with api.session() as db:
        db.add(AudioFile(recording_id=identifier, file_role=FileRole.ORIGINAL,
            storage_path=f"recordings/{uuid4()}.wav", mime_type="audio/wav", file_size_bytes=1))
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize("content,status", [(b"", 422), (b"not audio", 422)])
def test_invalid_upload_becomes_failed_and_can_retry(api, audio_assets, content, status):
    identifier = create(api).json()["id"]
    response = api.client.post(f"/api/recordings/{identifier}/audio", files={"file": ("bad.wav", content, "audio/wav")})
    assert response.status_code == status
    assert api.client.get(f"/api/recordings/{identifier}").json()["status"] == "failed"
    assert not list(api.settings.storage_root.glob("recordings/*"))
    assert attach(api, identifier, audio_assets).status_code == 200


@pytest.mark.parametrize("setting,value,status", [("max_recording_size_bytes", 100, 413),
    ("max_recording_duration_seconds", .1, 422), ("ffprobe_path", "missing-voiceclean-ffprobe", 503)])
def test_lecture_limits_and_cleanup(api, audio_assets, setting, value, status):
    identifier = create(api).json()["id"]
    setattr(api.settings, setting, value)
    assert attach(api, identifier, audio_assets).status_code == status
    assert api.client.get(f"/api/recordings/{identifier}").json()["status"] == "failed"
    assert not list(api.settings.storage_root.glob("recordings/*"))


def test_lecture_limits_are_separate_from_references(api, audio_assets):
    owner = register(api)
    api.settings.max_reference_size_bytes = 100
    identifier = create(api, owner).json()["id"]
    assert attach(api, identifier, audio_assets).status_code == 200
    assert reference_upload(api, owner, audio_assets).status_code == 413


def test_recording_request_body_guard(api):
    api.settings.max_recording_size_bytes = 1
    response = api.client.post(f"/api/recordings/{uuid4()}/audio", content=b"",
        headers={"Content-Length": "70000"})
    assert response.status_code == 413


@pytest.mark.parametrize("fields", [{}, {"title": None}, {"title": " "}, {"status": "ready"}, {"lecturer_id": str(uuid4())}])
def test_patch_rejects_invalid_fields_and_status_changes(api, fields):
    identifier = create(api).json()["id"]
    assert api.client.patch(f"/api/recordings/{identifier}", json=fields).status_code == 422


def test_list_search_filters_and_rename(api):
    owner = register(api)
    first = create(api, owner, title="Fourier 100%", description="DSP filters").json()
    create(api, owner, title="Unrelated")
    page = api.client.get(f"/api/recordings?lecturer_id={owner}&limit=1&offset=0").json()
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert api.client.get(f"/api/recordings?lecturer_id={owner}&q=DSP").json()["total"] == 1
    assert api.client.get(f"/api/recordings?lecturer_id={owner}&q=%25").json()["total"] == 1
    assert api.client.get(f"/api/recordings?lecturer_id={owner}&status=ready").json()["total"] == 0
    edited = api.client.patch(f"/api/recordings/{first['id']}", json={"title": "Renamed", "description": None})
    assert edited.status_code == 200
    assert edited.json()["title"] == "Renamed"
    assert edited.json()["description"] is None
    assert edited.json()["updated_at"] > first["updated_at"]
    for query in ["limit=0", "limit=101", "offset=-1", "status=unknown"]:
        assert api.client.get("/api/recordings?" + query).status_code == 422


def test_upload_lock_prevents_concurrent_upload_edit_and_delete(api, audio_assets):
    identifier = create(api).json()["id"]
    with api.session() as db:
        db.execute(text("SELECT id FROM recordings WHERE id=:id FOR UPDATE"), {"id": identifier})
        assert attach(api, identifier, audio_assets).status_code == 409
        assert api.client.delete(f"/api/recordings/{identifier}").status_code == 409
        assert api.client.patch(f"/api/recordings/{identifier}", json={"title": "Busy"}).status_code == 409


def test_invalid_uploading_state_and_pending_stream(api, audio_assets):
    identifier = create(api).json()["id"]
    assert api.client.get(f"/api/recordings/{identifier}/stream").status_code == 409
    with api.session() as db:
        db.execute(text("UPDATE recordings SET status='uploading' WHERE id=:id"), {"id": identifier})
        db.commit()
    assert attach(api, identifier, audio_assets).status_code == 409


@pytest.mark.parametrize("failure,expected", [("fail_commit", 503), ("corrupt_commit", 409)])
def test_recording_rollback_cleans_new_file(api, audio_assets, failure, expected):
    identifier = create(api).json()["id"]
    setattr(api, failure, True)
    response = attach(api, identifier, audio_assets)
    assert response.status_code == expected, response.text
    setattr(api, failure, False)
    assert not list(api.settings.storage_root.glob("recordings/*"))
    value = api.client.get(f"/api/recordings/{identifier}").json()
    assert value["original_audio"] is None
    assert value["status"] in {"pending", "failed"}


def test_uncertain_committed_original_is_retained_and_reconciled(api, audio_assets):
    identifier = create(api).json()["id"]
    api.ambiguous_commit = True
    assert attach(api, identifier, audio_assets).status_code == 503
    api.ambiguous_commit = False
    value = api.client.get(f"/api/recordings/{identifier}").json()
    assert value["status"] == "ready"
    assert api.client.get(value["audio_url"]).content == audio_assets["wav"]
    assert attach(api, identifier, audio_assets).status_code == 409


def test_delete_removes_only_recording_and_associated_files(api, audio_assets):
    owner = register(api)
    reference = reference_upload(api, owner, audio_assets).json()
    identifier = create(api, owner).json()["id"]
    value = attach(api, identifier, audio_assets).json()
    extra = api.settings.storage_root / "exports" / f"{uuid4()}.mp3"
    extra.parent.mkdir()
    extra.write_bytes(b"export test bytes")
    with api.session() as db:
        db.add(AudioFile(recording_id=identifier, file_role=FileRole.EXPORTED,
            storage_path="exports/" + extra.name, mime_type="audio/mpeg", file_size_bytes=extra.stat().st_size))
        db.commit()
    other = create(api, owner).json()["id"]
    response = api.client.delete(f"/api/recordings/{identifier}")
    assert response.status_code == 200
    assert response.json()["file_cleanup_pending"] is False
    assert not extra.exists()
    assert api.client.get(value["audio_url"]).status_code == 404
    assert api.client.get(f"/api/recordings/{other}").status_code == 200
    assert api.client.get(reference["audio_url"]).status_code == 200


def test_failed_delete_keeps_existing_original(api, audio_assets):
    identifier = create(api).json()["id"]
    value = attach(api, identifier, audio_assets).json()
    api.fail_commit = True
    assert api.client.delete(f"/api/recordings/{identifier}").status_code == 503
    api.fail_commit = False
    assert api.client.get(value["audio_url"]).status_code == 200


def test_cleanup_failure_and_missing_file_behavior(api, audio_assets, monkeypatch):
    identifier = create(api).json()["id"]
    value = attach(api, identifier, audio_assets).json()
    next(api.settings.storage_root.glob("recordings/*")).unlink()
    assert api.client.get(value["audio_url"]).status_code == 404
    monkeypatch.setattr(api.recording_storage, "cleanup", lambda path: False)
    result = api.client.delete(f"/api/recordings/{identifier}")
    assert result.status_code == 200
    assert result.json()["file_cleanup_pending"] is True


def test_recording_persists_across_two_actual_api_restarts(api, audio_assets):
    identifier = create(api).json()["id"]
    value = attach(api, identifier, audio_assets, "webm").json()
    for _ in range(2):
        with live_api(api) as client:
            assert client.get(f"/api/recordings/{identifier}").json()["status"] == "ready"
            assert client.get(value["audio_url"]).content == audio_assets["webm"]
            assert client.get(value["audio_url"], headers={"Range": "bytes=0-9"}).status_code == 206


def test_real_vue_component_save_reload_and_api_restart(api, audio_assets):
    import os
    from pathlib import Path
    import shutil
    import subprocess

    root = Path(__file__).resolve().parents[2]
    asset = api.settings.storage_root / "frontend-fixture.wav"
    asset.write_bytes(audio_assets["wav"])
    artifact = api.settings.storage_root / "frontend-ids.json"
    node = shutil.which("node")
    assert node, "Node.js is required for the full frontend/API integration check"
    for mode in ["save", "restore"]:
        with live_api(api) as client:
            env = os.environ.copy()
            env.update({"VOICECLEAN_TEST_API_BASE_URL": str(client.base_url).rstrip('/'),
                        "VOICECLEAN_TEST_MODE": mode, "VOICECLEAN_TEST_AUDIO_FILE": str(asset),
                        "VOICECLEAN_TEST_IDS_FILE": str(artifact)})
            result = subprocess.run([node, "--test", "tests/integration/liveState.test.js"],
                cwd=root / "frontend", env=env, capture_output=True, text=True, timeout=90)
            assert result.returncode == 0, result.stdout + result.stderr

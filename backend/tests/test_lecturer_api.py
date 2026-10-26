from pathlib import Path
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import AudioFile, Recording, VoiceSample


def register(api, name="Dr. API Example"):
    response = api.client.post("/api/lecturers", json={"name": name, "department": "CPE"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(api, owner, assets, suffix="wav", filename=None):
    return api.client.post(f"/api/lecturers/{owner}/samples", data={"label": " Reference "},
        files={"file": (filename or f"sample.{suffix}", assets[suffix], "application/octet-stream")})


def test_register_get_patch_pagination_and_delete(api):
    owner = register(api, "  Dr. Trimmed  ")
    detail = api.client.get(f"/api/lecturers/{owner}").json()
    assert detail["name"] == "Dr. Trimmed"
    page = api.client.get("/api/lecturers?limit=1&offset=0")
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] >= 1
    assert page.json()["limit"] == 1
    changed = api.client.patch(f"/api/lecturers/{owner}", json={"name": "Updated", "department": None})
    assert changed.status_code == 200
    assert changed.json()["name"] == "Updated"
    assert changed.json()["department"] is None
    assert changed.json()["created_at"] == detail["created_at"]
    assert changed.json()["updated_at"] > detail["updated_at"]
    assert api.client.delete(f"/api/lecturers/{owner}").status_code == 204
    assert api.client.get(f"/api/lecturers/{owner}").status_code == 404


@pytest.mark.parametrize("payload", [{}, {"name": " "}, {"name": None}, {"name": "x" * 201},
    {"name": "Valid", "department": "x" * 201}, {"name": "Bad\u0000Name"},
    {"name": "Valid", "unknown": "field"}])
def test_lecturer_validation(api, payload):
    assert api.client.post("/api/lecturers", json=payload).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"name": " "}, {"department": "\u0000"}])
def test_patch_validation(api, payload):
    owner = register(api)
    assert api.client.patch(f"/api/lecturers/{owner}", json=payload).status_code == 422


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_pagination_validation(api, query):
    assert api.client.get("/api/lecturers?" + query).status_code == 422


def test_missing_and_invalid_lecturer_ids(api, audio_assets):
    owner = str(uuid4())
    assert api.client.get("/api/lecturers/not-a-uuid").status_code == 422
    assert api.client.patch(f"/api/lecturers/{owner}", json={"name": "Missing"}).status_code == 404
    assert api.client.delete(f"/api/lecturers/{owner}").status_code == 404
    assert api.client.get(f"/api/lecturers/{owner}/samples").status_code == 404
    assert upload(api, owner, audio_assets).status_code == 404
    assert not list(api.settings.storage_root.rglob("*.wav"))


@pytest.mark.parametrize("suffix", ["wav", "mp3", "webm"])
def test_upload_metadata_and_playback(api, audio_assets, suffix):
    owner = register(api)
    response = upload(api, owner, audio_assets, suffix)
    assert response.status_code == 201, response.text
    sample = response.json()
    metadata = sample["audio_file"]
    assert sample["label"] == "Reference"
    assert metadata["file_role"] == "reference"
    assert metadata["file_size_bytes"] == len(audio_assets[suffix])
    assert float(metadata["duration_seconds"]) > 0
    assert metadata["sample_rate_hz"] > 0
    assert metadata["channels"] == 1
    assert "storage_path" not in metadata
    with api.session() as db:
        value = db.get(VoiceSample, sample["id"])
        relative = value.audio_file.storage_path
        assert relative.startswith("references/")
        assert not Path(relative).is_absolute()
        assert value.audio_file.recording_id is None
        assert api.storage.path(relative).read_bytes() == audio_assets[suffix]
    playback = api.client.get(sample["audio_url"])
    assert playback.status_code == 200
    assert playback.content == audio_assets[suffix]
    assert playback.headers["content-type"] == {"wav": "audio/wav", "mp3": "audio/mpeg", "webm": "audio/webm"}[suffix]
    assert playback.headers["x-content-type-options"] == "nosniff"
    partial = api.client.get(sample["audio_url"], headers={"Range": "bytes=0-9"})
    assert partial.status_code == 206
    assert partial.content == audio_assets[suffix][:10]
    listed = api.client.get(f"/api/lecturers/{owner}/samples").json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == sample["id"]
    assert api.client.get(f"/api/lecturers/{owner}/samples/{sample['id']}").status_code == 200
    assert not list(api.settings.storage_root.rglob(".upload-*"))


@pytest.mark.parametrize("name,content,status", [
    ("empty.wav", b"", 422), ("fake.wav", b"not audio", 422),
    ("sample.exe", b"not audio", 415), ("../bad.wav", b"bad", 422),
    ("..\\bad.wav", b"bad", 422), ("a:b.wav", b"bad", 422),
])
def test_reject_invalid_uploads(api, name, content, status):
    owner = register(api)
    response = api.client.post(f"/api/lecturers/{owner}/samples", files={"file": (name, content, "audio/wav")})
    assert response.status_code == status, response.text
    assert not list(api.settings.storage_root.rglob("*.wav"))
    with api.session() as db:
        assert db.scalar(select(func.count()).select_from(VoiceSample).where(VoiceSample.lecturer_id == owner)) == 0


def test_format_extension_mismatch(api, audio_assets):
    owner = register(api)
    response = upload(api, owner, audio_assets, "wav", filename="pretend.mp3")
    assert response.status_code == 415


def test_video_content_cannot_masquerade_as_reference(api, audio_assets):
    owner = register(api)
    response = api.client.post(f"/api/lecturers/{owner}/samples",
        files={"file": ("video.webm", audio_assets["video"], "audio/webm")})
    assert response.status_code == 415
    assert not list(api.settings.storage_root.rglob("*.webm"))


@pytest.mark.parametrize("label", ["x" * 201, "bad\u0000label"])
def test_sample_label_validation(api, audio_assets, label):
    owner = register(api)
    response = api.client.post(f"/api/lecturers/{owner}/samples", data={"label": label},
        files={"file": ("sample.wav", audio_assets["wav"], "audio/wav")})
    assert response.status_code == 422
    assert not list(api.settings.storage_root.rglob("*.wav"))


def test_request_size_rejection_retains_cors_headers(api):
    response = api.client.post(f"/api/lecturers/{uuid4()}/samples", content=b"",
        headers={"Content-Length": str(api.settings.max_reference_size_bytes + 65537),
                 "Origin": "http://localhost:5173"})
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_file_size_limit(api, audio_assets):
    owner = register(api)
    api.settings.max_reference_size_bytes = 100
    response = upload(api, owner, audio_assets)
    assert response.status_code == 413
    assert not list(api.settings.storage_root.rglob(".upload-*"))
    assert not list(api.settings.storage_root.rglob("*.wav"))


def test_request_body_limit_without_content_length(api):
    owner = register(api)
    api.settings.max_reference_size_bytes = 1
    boundary = b"----test"
    body = b"------test\r\nContent-Disposition: form-data; name=\"file\"; filename=\"large.wav\"\r\n\r\n" + b"x" * 70000 + b"\r\n------test--\r\n"
    response = api.client.post(f"/api/lecturers/{owner}/samples", content=iter([body[:40000], body[40000:]]),
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary.decode()})
    assert response.status_code == 413, response.text


def test_duration_limit(api, audio_assets):
    owner = register(api)
    api.settings.max_reference_duration_seconds = .1
    assert upload(api, owner, audio_assets).status_code == 422
    assert not list(api.settings.storage_root.rglob("*.wav"))


def test_ffprobe_unavailable(api, audio_assets):
    owner = register(api)
    api.settings.ffprobe_path = "voiceclean-missing-ffprobe"
    assert upload(api, owner, audio_assets).status_code == 503
    assert not list(api.settings.storage_root.rglob("*.wav"))


def test_ffprobe_timeout_cleans_staging(api, audio_assets, monkeypatch):
    owner = register(api)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ffprobe", 1)
    monkeypatch.setattr("app.services.reference_storage.subprocess.run", timeout)
    assert upload(api, owner, audio_assets).status_code == 422
    assert not list(api.settings.storage_root.rglob(".upload-*"))


def test_lecturer_with_sample_cannot_be_deleted(api, audio_assets):
    owner = register(api)
    assert upload(api, owner, audio_assets).status_code == 201
    response = api.client.delete(f"/api/lecturers/{owner}")
    assert response.status_code == 409
    assert "reference samples" in response.json()["detail"]


def test_lecturer_with_recording_cannot_be_deleted(api):
    owner = register(api)
    with api.session() as db:
        db.add(Recording(lecturer_id=owner, title="Conflict test"))
        db.commit()
    assert api.client.delete(f"/api/lecturers/{owner}").status_code == 409


@pytest.mark.parametrize("method,suffix", [("get", ""), ("get", "/audio"), ("delete", "")])
def test_cross_lecturer_access_blocked(api, audio_assets, method, suffix):
    owner, other = register(api), register(api)
    sample = upload(api, owner, audio_assets).json()
    response = getattr(api.client, method)(f"/api/lecturers/{other}/samples/{sample['id']}{suffix}")
    assert response.status_code == 404
    assert api.client.get(sample["audio_url"]).status_code == 200


@pytest.mark.parametrize("failure,status", [("fail_commit", 503), ("corrupt_commit", 409)])
def test_database_rollback_cleans_uploaded_files(api, audio_assets, failure, status):
    owner = register(api)
    setattr(api, failure, True)
    response = upload(api, owner, audio_assets)
    assert response.status_code == status, response.text
    setattr(api, failure, False)
    assert "private" not in response.text
    assert not list(api.settings.storage_root.rglob("*.wav"))
    with api.session() as db:
        assert db.scalar(select(func.count()).select_from(VoiceSample).where(VoiceSample.lecturer_id == owner)) == 0


def test_sample_deletion_removes_pair_and_file(api, audio_assets):
    owner = register(api)
    sample = upload(api, owner, audio_assets).json()
    response = api.client.delete(f"/api/lecturers/{owner}/samples/{sample['id']}")
    assert response.status_code == 200
    assert response.json()["file_cleanup_pending"] is False
    assert api.client.get(sample["audio_url"]).status_code == 404
    assert not list(api.settings.storage_root.rglob("*.wav"))
    with api.session() as db:
        assert db.get(VoiceSample, sample["id"]) is None
        assert db.get(AudioFile, sample["audio_file"]["id"]) is None
    assert api.client.delete(f"/api/lecturers/{owner}").status_code == 204


def test_uncertain_commit_does_not_remove_committed_audio(api, audio_assets):
    owner = register(api)
    api.ambiguous_commit = True
    assert upload(api, owner, audio_assets).status_code == 503
    api.ambiguous_commit = False
    page = api.client.get(f"/api/lecturers/{owner}/samples").json()
    assert page["total"] == 1
    assert api.client.get(page["items"][0]["audio_url"]).status_code == 200


def test_missing_physical_file_can_still_remove_metadata(api, audio_assets):
    owner = register(api)
    sample = upload(api, owner, audio_assets).json()
    next(api.settings.storage_root.rglob("*.wav")).unlink()
    assert api.client.get(sample["audio_url"]).status_code == 404
    response = api.client.delete(f"/api/lecturers/{owner}/samples/{sample['id']}")
    assert response.status_code == 200
    assert response.json()["file_cleanup_pending"] is False


def test_failed_deletion_keeps_file_and_metadata(api, audio_assets):
    owner = register(api)
    sample = upload(api, owner, audio_assets).json()
    api.fail_commit = True
    assert api.client.delete(f"/api/lecturers/{owner}/samples/{sample['id']}").status_code == 503
    api.fail_commit = False
    assert api.client.get(sample["audio_url"]).status_code == 200


def test_file_cleanup_failure_is_reported_after_commit(api, audio_assets, monkeypatch):
    owner = register(api)
    sample = upload(api, owner, audio_assets).json()
    monkeypatch.setattr(api.storage, "cleanup", lambda path: False)
    response = api.client.delete(f"/api/lecturers/{owner}/samples/{sample['id']}")
    assert response.status_code == 200
    assert response.json()["file_cleanup_pending"] is True
    assert api.client.get(sample["audio_url"]).status_code == 404
    assert len(list(api.settings.storage_root.rglob("*.wav"))) == 1


def test_stored_path_traversal_rejected(api, audio_assets):
    owner = register(api)
    sample = upload(api, owner, audio_assets).json()
    with api.session() as db:
        file = db.get(AudioFile, sample["audio_file"]["id"])
        file.storage_path = "references/../../outside.wav"
        db.commit()
    assert api.client.get(sample["audio_url"]).status_code == 503
    assert api.client.delete(f"/api/lecturers/{owner}/samples/{sample['id']}").status_code == 503


def test_cors_allows_reference_mutations(api):
    for method in ["POST", "PATCH", "DELETE"]:
        response = api.client.options("/api/lecturers", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 200


def test_saved_reference_survives_fresh_requests_and_two_api_process_restarts(api, audio_assets):
    from tests.server_process import live_api
    owner = register(api)
    saved = upload(api, owner, audio_assets).json()
    for _ in range(2):
        with live_api(api) as client:
            assert client.get(f"/api/lecturers/{owner}").status_code == 200
            page = client.get(f"/api/lecturers/{owner}/samples").json()
            assert page["items"][0]["id"] == saved["id"]
            assert client.get(saved["audio_url"]).content == audio_assets["wav"]
            assert client.get(f"/api/lecturers/{owner}/samples/{saved['id']}").status_code == 200

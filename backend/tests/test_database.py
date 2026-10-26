"""Real PostgreSQL tests: migrated private schema, rolled-back per-test transactions.

No application rows are inserted or deleted in public. The only schema dropped
is the randomly named test schema created by this module's fixture.
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AudioFile, FileRole, Lecturer, Recording, RecordingStatus, VoiceSample


@pytest.fixture
def db(isolated_database):
    engine, schema = isolated_database
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            try:
                yield session
            finally:
                session.close()
                if transaction.is_active:
                    transaction.rollback()


def enforce_deferred(db):
    db.flush()
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    db.execute(text("SET CONSTRAINTS ALL DEFERRED"))


def lecturer(db):
    value = Lecturer(name="Dr. Example", department="Computer Engineering")
    db.add(value)
    db.flush()
    return value


def recording(db, owner=None):
    value = Recording(lecturer=owner or lecturer(db), title="DSP lecture")
    db.add(value)
    db.flush()
    return value


def audio(**overrides):
    values = dict(
        file_role=FileRole.REFERENCE,
        storage_path=f"references/{uuid4()}.webm",
        mime_type="audio/webm",
        file_size_bytes=1000,
        duration_seconds=Decimal("2.500"),
        sample_rate_hz=48000,
        channels=1,
    )
    values.update(overrides)
    return AudioFile(**values)


def reference(db, owner=None):
    value = VoiceSample(lecturer=owner or lecturer(db), audio_file=audio(), label="Reference")
    db.add(value)
    enforce_deferred(db)
    return value


def test_create_lecturer_and_recording(db):
    value = recording(db)
    assert isinstance(value.id, UUID)
    assert isinstance(value.lecturer.id, UUID)
    assert value.status is RecordingStatus.PENDING
    assert value.lecturer.name == "Dr. Example"
    assert value.created_at.tzinfo is not None
    assert value.recorded_at is None


def test_reference_and_relationships(db):
    value = reference(db)
    assert value.audio_file.recording_id is None
    assert value.audio_file.file_role is FileRole.REFERENCE
    db.expire_all()
    assert value.audio_file.voice_sample is value
    assert value in value.lecturer.voice_samples


def test_multiple_samples_recordings_and_original_preservation(db):
    owner = lecturer(db)
    samples = [reference(db, owner), reference(db, owner)]
    recordings = [recording(db, owner), recording(db, owner)]
    files = [audio(recording=recordings[0], file_role=role,
                   storage_path=f"recordings/{uuid4()}.webm")
             for role in [FileRole.ORIGINAL, FileRole.EXPORTED, FileRole.PROCESSED]]
    db.add_all(files)
    enforce_deferred(db)
    original_id, original_path = files[0].id, files[0].storage_path
    db.expire_all()
    assert set(owner.voice_samples) == set(samples)
    assert set(owner.recordings) == set(recordings)
    assert set(recordings[0].audio_files) == set(files)
    assert db.get(AudioFile, original_id).storage_path == original_path
    assert db.get(AudioFile, original_id).file_role is FileRole.ORIGINAL


@pytest.mark.parametrize("entity,field", [
    ("recording", "lecturer_id"), ("sample", "lecturer_id"),
    ("sample", "audio_file_id"), ("audio", "recording_id"),
])
def test_foreign_keys(db, entity, field):
    if entity == "recording":
        value = Recording(lecturer_id=uuid4(), title="Invalid")
    elif entity == "audio":
        value = audio(file_role=FileRole.ORIGINAL, recording_id=uuid4())
    else:
        value = VoiceSample(lecturer_id=lecturer(db).id, audio_file_id=reference(db).audio_file_id)
        setattr(value, field, uuid4())
    db.add(value)
    with pytest.raises(IntegrityError):
        enforce_deferred(db)


def test_voice_samples_cannot_share_audio(db):
    value = reference(db)
    db.add(VoiceSample(lecturer_id=value.lecturer_id, audio_file_id=value.audio_file_id))
    with pytest.raises(IntegrityError):
        db.flush()


def test_storage_path_cannot_be_shared(db):
    value = reference(db)
    db.add(audio(storage_path=value.audio_file.storage_path))
    with pytest.raises(IntegrityError):
        db.flush()


def test_invalid_status_is_rejected_by_database(db):
    value = recording(db)
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE recordings SET status = 'unknown' WHERE id = :id"), {"id": value.id})


def test_invalid_file_role_is_rejected_by_database(db):
    value = reference(db)
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE audio_files SET file_role = 'unknown' WHERE id = :id"), {"id": value.audio_file_id})


@pytest.mark.parametrize("field,value", [
    ("file_size_bytes", -1), ("duration_seconds", Decimal("-0.001")),
    ("duration_seconds", Decimal("NaN")), ("sample_rate_hz", 0),
    ("sample_rate_hz", -1), ("channels", 0), ("channels", -1),
])
def test_invalid_audio_numbers(db, field, value):
    db.add(audio(**{field: value}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_zero_size_duration_and_optional_metadata(db):
    value = audio(file_size_bytes=0, duration_seconds=0, sample_rate_hz=None, channels=None)
    db.add(VoiceSample(lecturer=lecturer(db), audio_file=value))
    enforce_deferred(db)
    assert value.duration_seconds == 0


@pytest.mark.parametrize("model,values", [
    (Lecturer, {"name": None}), (Lecturer, {"name": "   "}),
    (Recording, {"title": None}), (Recording, {"title": " "}),
    (AudioFile, {"storage_path": " "}), (AudioFile, {"mime_type": ""}),
    (AudioFile, {"mime_type": None}), (AudioFile, {"file_size_bytes": None}),
])
def test_required_values(db, model, values):
    if model is Lecturer:
        value = Lecturer(**values)
    elif model is Recording:
        value = Recording(lecturer=lecturer(db), **values)
    else:
        value = audio(**values)
    db.add(value)
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize("role", [FileRole.ORIGINAL, FileRole.EXPORTED, FileRole.PROCESSED])
def test_recording_roles_require_recording(db, role):
    db.add(audio(file_role=role))
    with pytest.raises(IntegrityError):
        db.flush()


def test_reference_cannot_belong_to_recording(db):
    db.add(audio(recording=recording(db)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_orphan_reference_rejected(db):
    db.add(audio())
    with pytest.raises(IntegrityError):
        enforce_deferred(db)


def test_voice_sample_cannot_reference_recording_audio(db):
    value = audio(file_role=FileRole.ORIGINAL, recording=recording(db))
    owner = value.recording.lecturer
    db.add(VoiceSample(lecturer=owner, audio_file=value))
    with pytest.raises(IntegrityError):
        enforce_deferred(db)


def test_deleting_sample_alone_rejected(db):
    value = reference(db)
    db.delete(value)
    with pytest.raises(IntegrityError):
        enforce_deferred(db)


def test_reference_and_sample_can_be_deleted_together(db):
    value = reference(db)
    file = value.audio_file
    db.delete(value)
    db.flush()
    db.delete(file)
    enforce_deferred(db)
    assert db.get(AudioFile, file.id) is None


def test_reassigning_sample_cannot_orphan_original_reference(db):
    value = reference(db)
    value.audio_file = audio()
    with pytest.raises(IntegrityError):
        enforce_deferred(db)


def test_changing_reference_role_cannot_leave_sample_on_recording_audio(db):
    value = reference(db)
    value.audio_file.recording = recording(db)
    value.audio_file.file_role = FileRole.ORIGINAL
    with pytest.raises(IntegrityError):
        enforce_deferred(db)


@pytest.mark.parametrize("target", ["lecturer", "recording", "reference_audio"])
def test_parent_deletion_restricted(db, target):
    if target == "lecturer":
        value = recording(db).lecturer
    elif target == "recording":
        value = recording(db)
        db.add(audio(file_role=FileRole.ORIGINAL, recording=value))
        enforce_deferred(db)
    else:
        value = reference(db).audio_file
    db.delete(value)
    with pytest.raises(IntegrityError):
        db.flush()


def test_timestamps_update_for_orm_and_direct_sql(db):
    value = recording(db)
    owner = value.lecturer
    created, old_updated = value.created_at, value.updated_at
    owner_created, owner_updated = owner.created_at, owner.updated_at
    value.title = "Updated lecture"
    db.flush()
    db.refresh(value)
    assert value.created_at == created
    assert value.updated_at > old_updated
    assert value.updated_at.tzinfo is not None
    db.execute(text("UPDATE lecturers SET department = 'DSP' WHERE id = :id"), {"id": owner.id})
    db.refresh(owner)
    assert owner.created_at == owner_created
    assert owner.updated_at > owner_updated


def test_raw_insert_database_defaults(db):
    row = db.execute(text("INSERT INTO lecturers (name) VALUES ('SQL insert') RETURNING id, created_at, updated_at")).one()
    assert isinstance(row.id, UUID)
    assert row.created_at.tzinfo is not None
    assert row.updated_at.tzinfo is not None
    value = db.execute(text("INSERT INTO recordings (lecturer_id, title) VALUES (:id, 'SQL recording') RETURNING status"), {"id": row.id}).scalar_one()
    assert value == "pending"


def test_schema_matches_metadata(db):
    inspector = inspect(db.connection())
    for model in (Lecturer, Recording, AudioFile, VoiceSample):
        actual = {column["name"]: column for column in inspector.get_columns(model.__tablename__)}
        assert set(actual) == set(model.__table__.columns.keys())
        assert str(actual["id"]["type"]) == "UUID"
        assert actual["created_at"]["type"].timezone


def test_orphan_reference_fails_at_real_commit(isolated_database):
    engine, schema = isolated_database
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        connection.execute(text("""
            INSERT INTO audio_files (file_role, storage_path, mime_type, file_size_bytes)
            VALUES ('reference', :path, 'audio/webm', 1)
        """), {"path": f"references/{uuid4()}.webm"})
        with pytest.raises(IntegrityError):
            transaction.commit()
        connection.rollback()


def test_reference_pair_succeeds_at_real_commit(isolated_database):
    engine, schema = isolated_database
    with engine.connect() as connection:
        connection.execute(text(f'SET search_path TO "{schema}", public'))
        connection.commit()
        with Session(bind=connection) as session:
            value = VoiceSample(lecturer=Lecturer(name="Committed test lecturer"), audio_file=audio())
            session.add(value)
            session.flush()
            sample_id = value.id
            session.commit()
        # A new transaction can see the successfully committed pair.
        with Session(bind=connection) as session:
            value = session.get(VoiceSample, sample_id)
            assert value is not None
            assert value.audio_file.file_role is FileRole.REFERENCE
            assert value.audio_file.voice_sample is value

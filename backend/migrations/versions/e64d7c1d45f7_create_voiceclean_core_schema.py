"""Create VoiceClean core schema

Revision ID: e64d7c1d45f7
Revises: 
Create Date: 2026-10-26 16:50:21.493622
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e64d7c1d45f7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Generated from model metadata, then reviewed and extended with DB triggers.
    op.create_table('lecturers',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('department', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(name) <> ''", name='ck_lecturers_name_nonempty'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lecturers_created_at', 'lecturers', ['created_at'], unique=False)
    op.create_index('ix_lecturers_name', 'lecturers', ['name'], unique=False)
    op.create_table('recordings',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('lecturer_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=250), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('pending', 'uploading', 'ready', 'failed', name='ck_recordings_status', native_enum=False, create_constraint=True, length=16), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(title) <> ''", name='ck_recordings_title_nonempty'),
    sa.ForeignKeyConstraint(['lecturer_id'], ['lecturers.id'], name='fk_recordings_lecturer_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recordings_created_at', 'recordings', ['created_at'], unique=False)
    op.create_index('ix_recordings_lecturer_created_at', 'recordings', ['lecturer_id', 'created_at'], unique=False)
    op.create_index('ix_recordings_status', 'recordings', ['status'], unique=False)
    op.create_table('audio_files',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('recording_id', sa.Uuid(), nullable=True),
    sa.Column('file_role', sa.Enum('reference', 'original', 'exported', 'processed', name='ck_audio_files_file_role', native_enum=False, create_constraint=True, length=16), nullable=False),
    sa.Column('storage_path', sa.String(length=1024), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=True),
    sa.Column('mime_type', sa.String(length=127), nullable=False),
    sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('duration_seconds', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('sample_rate_hz', sa.Integer(), nullable=True),
    sa.Column('channels', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(file_role = 'reference' AND recording_id IS NULL) OR (file_role IN ('original', 'exported', 'processed') AND recording_id IS NOT NULL)", name='ck_audio_files_role_recording'),
    sa.CheckConstraint("btrim(mime_type) <> ''", name='ck_audio_files_mime_type_nonempty'),
    sa.CheckConstraint("btrim(storage_path) <> ''", name='ck_audio_files_storage_path_nonempty'),
    sa.CheckConstraint('channels > 0', name='ck_audio_files_channels_positive'),
    sa.CheckConstraint("duration_seconds >= 0 AND duration_seconds <> 'NaN'::numeric", name='ck_audio_files_duration_nonnegative'),
    sa.CheckConstraint('file_size_bytes >= 0', name='ck_audio_files_size_nonnegative'),
    sa.CheckConstraint('sample_rate_hz > 0', name='ck_audio_files_sample_rate_positive'),
    sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], name='fk_audio_files_recording_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_path', name='uq_audio_files_storage_path')
    )
    op.create_index('ix_audio_files_created_at', 'audio_files', ['created_at'], unique=False)
    op.create_index('ix_audio_files_recording_role', 'audio_files', ['recording_id', 'file_role'], unique=False)
    op.create_table('voice_samples',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('lecturer_id', sa.Uuid(), nullable=False),
    sa.Column('audio_file_id', sa.Uuid(), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['audio_file_id'], ['audio_files.id'], name='fk_voice_samples_audio_file_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['lecturer_id'], ['lecturers.id'], name='fk_voice_samples_lecturer_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('audio_file_id', name='uq_voice_samples_audio_file_id')
    )
    op.create_index('ix_voice_samples_lecturer_created_at', 'voice_samples', ['lecturer_id', 'created_at'], unique=False)
    # Row CHECK constraints cannot validate the inverse one-to-one relationship.
    # Defer cross-table checks until commit so a reference and its voice sample
    # can be inserted/deleted together without circular foreign keys.
    op.execute("""
        CREATE FUNCTION voiceclean_validate_audio_owner(target_id uuid)
        RETURNS void LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        DECLARE
            audio_role varchar;
            sample_count integer;
        BEGIN
            SELECT file_role INTO audio_role FROM audio_files
            WHERE id = target_id FOR UPDATE;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            SELECT count(*) INTO sample_count FROM voice_samples
            WHERE audio_file_id = target_id;
            IF (audio_role = 'reference' AND sample_count <> 1)
               OR (audio_role <> 'reference' AND sample_count <> 0) THEN
                RAISE EXCEPTION 'Audio role and voice sample ownership do not match'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_audio_files_voice_sample_owner';
            END IF;
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION voiceclean_check_audio_owner()
        RETURNS trigger LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
        BEGIN
            IF TG_TABLE_NAME = 'audio_files' THEN
                PERFORM voiceclean_validate_audio_owner(NEW.id);
            ELSE
                IF TG_OP IN ('UPDATE', 'DELETE') THEN
                    PERFORM voiceclean_validate_audio_owner(OLD.audio_file_id);
                END IF;
                IF TG_OP IN ('INSERT', 'UPDATE') THEN
                    PERFORM voiceclean_validate_audio_owner(NEW.audio_file_id);
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER ct_audio_files_voice_sample_owner
        AFTER INSERT OR UPDATE ON audio_files
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION voiceclean_check_audio_owner()
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER ct_voice_samples_audio_owner
        AFTER INSERT OR UPDATE OR DELETE ON voice_samples
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION voiceclean_check_audio_owner()
    """)
    op.execute("""
        CREATE FUNCTION voiceclean_touch_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = clock_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    for table in ("lecturers", "recordings"):
        op.execute(f"""
            CREATE TRIGGER tr_{table}_updated_at BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION voiceclean_touch_updated_at()
        """)


def downgrade() -> None:
    # Only use downgrade intentionally; it removes these application tables.
    op.execute("DROP TRIGGER tr_recordings_updated_at ON recordings")
    op.execute("DROP TRIGGER tr_lecturers_updated_at ON lecturers")
    op.execute("DROP FUNCTION voiceclean_touch_updated_at()")
    op.execute("DROP TRIGGER ct_voice_samples_audio_owner ON voice_samples")
    op.execute("DROP TRIGGER ct_audio_files_voice_sample_owner ON audio_files")
    op.execute("DROP FUNCTION voiceclean_check_audio_owner()")
    op.execute("DROP FUNCTION voiceclean_validate_audio_owner(uuid)")
    op.drop_index('ix_voice_samples_lecturer_created_at', table_name='voice_samples')
    op.drop_table('voice_samples')
    op.drop_index('ix_audio_files_recording_role', table_name='audio_files')
    op.drop_index('ix_audio_files_created_at', table_name='audio_files')
    op.drop_table('audio_files')
    op.drop_index('ix_recordings_status', table_name='recordings')
    op.drop_index('ix_recordings_lecturer_created_at', table_name='recordings')
    op.drop_index('ix_recordings_created_at', table_name='recordings')
    op.drop_table('recordings')
    op.drop_index('ix_lecturers_name', table_name='lecturers')
    op.drop_index('ix_lecturers_created_at', table_name='lecturers')
    op.drop_table('lecturers')

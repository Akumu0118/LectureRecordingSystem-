"""Enforce one original audio file per recording

Revision ID: f1f6a031e255
Revises: e64d7c1d45f7
Create Date: 2026-10-26 17:36:48.447409
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1f6a031e255'
down_revision: Union[str, Sequence[str], None] = 'e64d7c1d45f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reviewed metadata-generated partial index; no tables or data are removed.
    op.create_index('uq_audio_files_original_recording', 'audio_files', ['recording_id'], unique=True, postgresql_where=sa.text("file_role = 'original'"))


def downgrade() -> None:
    op.drop_index('uq_audio_files_original_recording', table_name='audio_files', postgresql_where=sa.text("file_role = 'original'"))

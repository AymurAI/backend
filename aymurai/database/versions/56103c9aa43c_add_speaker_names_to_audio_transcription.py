"""add speaker_names to audio_transcription

Revision ID: 56103c9aa43c
Revises: 49b3f24f7ad0
Create Date: 2026-04-21 14:01:04.905492

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "56103c9aa43c"
down_revision: Union[str, None] = "49b3f24f7ad0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_transcription",
        sa.Column(
            "speaker_names",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("audio_transcription", "speaker_names")

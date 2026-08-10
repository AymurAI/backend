"""Add llm validated destinatario table

Revision ID: 7e93b6df5d3c
Revises: 672b617e1980
Create Date: 2026-08-10 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e93b6df5d3c"
down_revision: Union[str, None] = "672b617e1980"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_validated_destinatario",
        sa.Column("nombre", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cargo", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sector", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "nombre_normalizado", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("nombre_normalizado"),
    )


def downgrade() -> None:
    op.drop_table("llm_validated_destinatario")

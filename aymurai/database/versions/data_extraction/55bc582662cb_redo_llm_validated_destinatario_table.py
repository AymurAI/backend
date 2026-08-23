"""Redo llm validated destinatario table (numeric id, document_id, cargo lookup)

Revision ID: 55bc582662cb
Revises: 7e93b6df5d3c
Create Date: 2026-08-21 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "55bc582662cb"
down_revision: Union[str, None] = "7e93b6df5d3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite can't ALTER a primary key in place -- drop and recreate. This
    # table is a derived lookup index (rebuilt from human validations, not a
    # source of truth), so dropping it is safe even with pre-existing rows.
    op.drop_table("llm_validated_destinatario")
    op.create_table(
        "llm_validated_destinatario",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "nombre_normalizado", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("cargo", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "cargo_normalizado", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("sector", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_validated_destinatario_nombre_normalizado"),
        "llm_validated_destinatario",
        ["nombre_normalizado"],
    )
    op.create_index(
        op.f("ix_llm_validated_destinatario_cargo_normalizado"),
        "llm_validated_destinatario",
        ["cargo_normalizado"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_llm_validated_destinatario_cargo_normalizado"),
        table_name="llm_validated_destinatario",
    )
    op.drop_index(
        op.f("ix_llm_validated_destinatario_nombre_normalizado"),
        table_name="llm_validated_destinatario",
    )
    op.drop_table("llm_validated_destinatario")
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

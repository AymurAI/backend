from datetime import datetime

from sqlalchemy import Column, DateTime, func, text
from sqlmodel import Field, SQLModel


class ValidatedDestinatarioBase(SQLModel):
    """Shared columns for a human-confirmed destinatario -> sector mapping."""

    nombre: str = Field(nullable=False)
    cargo: str | None = Field(default=None)
    sector: str = Field(nullable=False)


class ValidatedDestinatario(ValidatedDestinatarioBase, table=True):
    """
    A validated destinatario, keyed by `nombre_normalizado`.

    `nombre_normalizado` is `organigram_matching.normalize_text(nombre)`
    (lowercased, accent-stripped) -- the exact-match lookup key used to
    suggest a previously human-confirmed sector before falling back to the
    organigram inference. Upserted every time a human confirms/corrects a
    destinatario's sector.
    """

    __tablename__ = "llm_validated_destinatario"  # type: ignore[bad-override]
    nombre_normalizado: str = Field(primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(), onupdate=func.now())
    )


class ValidatedDestinatarioCreate(ValidatedDestinatarioBase):
    nombre_normalizado: str


class ValidatedDestinatarioUpdate(SQLModel):
    nombre: str | None = None
    cargo: str | None = None
    sector: str | None = None


class ValidatedDestinatarioRead(ValidatedDestinatarioBase):
    nombre_normalizado: str
    created_at: datetime
    updated_at: datetime | None = None

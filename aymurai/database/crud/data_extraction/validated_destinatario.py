import uuid

from sqlmodel import Session, select

from aymurai.database.schema import ValidatedDestinatario


def validated_destinatario_get_by_nombre(
    nombre_normalizado: str,
    session: Session,
) -> ValidatedDestinatario | None:
    """
    Get the most recently validated destinatario by normalized nombre.

    Args:
        nombre_normalizado (str): Normalized nombre (see
            `organigram_matching.normalize_text`), used as the lookup key.
        session (Session): SQLAlchemy session.

    Returns:
        ValidatedDestinatario | None: The most recent match (highest `id`),
        or None if this nombre was never validated.
    """
    statement = (
        select(ValidatedDestinatario)
        .where(ValidatedDestinatario.nombre_normalizado == nombre_normalizado)
        .order_by(ValidatedDestinatario.id.desc())
    )
    return session.exec(statement).first()


def validated_destinatario_get_by_cargo(
    cargo_normalizado: str,
    session: Session,
) -> ValidatedDestinatario | None:
    """
    Get the most recently validated destinatario by normalized cargo.

    Fallback for when no nombre match exists -- e.g. the same office/role was
    validated before under a different (or missing) nombre.

    Args:
        cargo_normalizado (str): Normalized cargo (see
            `organigram_matching.normalize_text`), used as the lookup key.
        session (Session): SQLAlchemy session.

    Returns:
        ValidatedDestinatario | None: The most recent match (highest `id`),
        or None if this cargo was never validated.
    """
    statement = (
        select(ValidatedDestinatario)
        .where(ValidatedDestinatario.cargo_normalizado == cargo_normalizado)
        .order_by(ValidatedDestinatario.id.desc())
    )
    return session.exec(statement).first()


def validated_destinatario_create_or_update(
    document_id: uuid.UUID,
    nombre: str,
    nombre_normalizado: str,
    cargo: str | None,
    cargo_normalizado: str | None,
    sector: str,
    session: Session,
) -> ValidatedDestinatario:
    """
    Create or update the validated sector for a destinatario in one document.

    Keyed by (`document_id`, `nombre_normalizado`): re-validating the same
    document updates its row; the same person validated in a *different*
    document gets a new row, preserving history across documents.

    Args:
        document_id (uuid.UUID): document_id of the DataExtraction this
            validation came from.
        nombre (str): Nombre as confirmed by a human.
        nombre_normalizado (str): Normalized nombre, used as (part of) the
            lookup key.
        cargo (str | None): Cargo as confirmed by a human.
        cargo_normalizado (str | None): Normalized cargo, used for the
            cargo-fallback lookup.
        sector (str): Sector as confirmed by a human.
        session (Session): SQLAlchemy session.

    Returns:
        ValidatedDestinatario: The created or updated record.
    """
    statement = select(ValidatedDestinatario).where(
        ValidatedDestinatario.document_id == document_id,
        ValidatedDestinatario.nombre_normalizado == nombre_normalizado,
    )
    record = session.exec(statement).first()

    if not record:
        record = ValidatedDestinatario(
            document_id=document_id,
            nombre=nombre,
            nombre_normalizado=nombre_normalizado,
            cargo=cargo,
            cargo_normalizado=cargo_normalizado,
            sector=sector,
        )
    else:
        record.nombre = nombre
        record.cargo = cargo
        record.cargo_normalizado = cargo_normalizado
        record.sector = sector

    session.add(record)
    session.commit()
    session.refresh(record)
    return record

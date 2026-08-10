from sqlmodel import Session

from aymurai.database.schema import ValidatedDestinatario


def validated_destinatario_get(
    nombre_normalizado: str,
    session: Session,
) -> ValidatedDestinatario | None:
    """
    Get a previously-validated destinatario by normalized nombre.

    Args:
        nombre_normalizado (str): Normalized nombre (see
            `organigram_matching.normalize_text`), used as the lookup key.
        session (Session): SQLAlchemy session.

    Returns:
        ValidatedDestinatario | None: The validated record, if any.
    """
    return session.get(ValidatedDestinatario, nombre_normalizado)


def validated_destinatario_create_or_update(
    nombre_normalizado: str,
    nombre: str,
    cargo: str | None,
    sector: str,
    session: Session,
) -> ValidatedDestinatario:
    """
    Create or update the validated sector for a destinatario.

    Args:
        nombre_normalizado (str): Normalized nombre, used as the lookup key.
        nombre (str): Nombre as last confirmed by a human.
        cargo (str | None): Cargo as last confirmed by a human.
        sector (str): Sector as confirmed by a human.
        session (Session): SQLAlchemy session.

    Returns:
        ValidatedDestinatario: The created or updated record.
    """
    record = session.get(ValidatedDestinatario, nombre_normalizado)

    if not record:
        record = ValidatedDestinatario(
            nombre_normalizado=nombre_normalizado,
            nombre=nombre,
            cargo=cargo,
            sector=sector,
        )
    else:
        record.nombre = nombre
        record.cargo = cargo
        record.sector = sector

    session.add(record)
    session.commit()
    session.refresh(record)
    return record

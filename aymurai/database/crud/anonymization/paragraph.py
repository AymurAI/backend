import uuid

from pydantic import TypeAdapter
from sqlmodel import Session

from aymurai.database.schema import (
    AnonymizationParagraph,
    AnonymizationParagraphCreate,
    AnonymizationParagraphUpdate,
)
from aymurai.database.utils import text_to_uuid
from aymurai.meta.api_interfaces import DocLabel


_DOC_LABELS_ADAPTER = TypeAdapter(list[DocLabel])


def _serialize_doclabels(value: list[DocLabel] | None):
    """
    Serializes DocLabel objects into JSON-compatible data structures.

    Args:
        value (list[DocLabel] | None): DocLabel list to serialize.

    Returns:
        list[dict] | None: JSON-safe list of labels, or None if input is None.
    """
    if value is None:
        return None
    return _DOC_LABELS_ADAPTER.dump_python(value, mode="json")


def _normalize_paragraph_payload(payload: dict) -> dict:
    """
    Normalizes paragraph payload fields for JSON storage.

    Args:
        payload (dict): Paragraph payload possibly containing DocLabel objects.

    Returns:
        dict: Payload with JSON-serializable prediction/validation fields.
    """
    if "prediction" in payload:
        payload["prediction"] = _serialize_doclabels(payload.get("prediction"))
    if "validation" in payload:
        payload["validation"] = _serialize_doclabels(payload.get("validation"))
    return payload


def anonymization_paragraph_create(
    paragraph_in: AnonymizationParagraphCreate,
    session: Session,
    override: bool = False,
) -> AnonymizationParagraph:
    """
    Creates a new anonymization paragraph record.

    Args:
        paragraph_in (AnonymizationParagraphCreate): Paragraph creation payload.
        session (Session): Database session.
        override (bool): If True, delete any existing paragraph with the same ID.

    Returns:
        AnonymizationParagraph: The persisted paragraph record.
    """
    payload = _normalize_paragraph_payload(paragraph_in.model_dump())
    new_paragraph = AnonymizationParagraph(**payload)

    if override:
        existing = session.get(AnonymizationParagraph, new_paragraph.id)

        if existing:
            session.delete(existing)

    session.add(new_paragraph)
    session.commit()
    session.refresh(new_paragraph)
    return new_paragraph


def anonymization_paragraph_read(
    paragraph_id: uuid.UUID,
    session: Session,
) -> AnonymizationParagraph | None:
    """
    Reads a paragraph record by ID.

    Args:
        paragraph_id (uuid.UUID): Paragraph UUID.
        session (Session): Database session.

    Returns:
        AnonymizationParagraph | None: Paragraph record if found.
    """
    return session.get(AnonymizationParagraph, paragraph_id)


def anonymization_paragraph_update(
    paragraph_id: uuid.UUID,
    paragraph_in: AnonymizationParagraphUpdate,
    session: Session,
) -> AnonymizationParagraph:
    """
    Updates an existing paragraph record.

    Args:
        paragraph_id (uuid.UUID): Paragraph UUID to update.
        paragraph_in (AnonymizationParagraphUpdate): Update payload.
        session (Session): Database session.

    Returns:
        AnonymizationParagraph: The updated paragraph record.
    """
    paragraph = session.get(AnonymizationParagraph, paragraph_id)

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    payload = _normalize_paragraph_payload(
        paragraph_in.model_dump(exclude_none=True, mode="json")
    )
    for field, value in payload.items():
        setattr(paragraph, field, value)

    session.add(paragraph)
    session.commit()
    session.refresh(paragraph)
    return paragraph


def anonymization_paragraph_delete(paragraph_id: uuid.UUID, session: Session):
    """
    Deletes a paragraph record by ID.

    Args:
        paragraph_id (uuid.UUID): Paragraph UUID to delete.
        session (Session): Database session.

    Returns:
        None
    """
    paragraph = session.get(AnonymizationParagraph, paragraph_id)

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    session.delete(paragraph)
    session.commit()

    return


# FIXME: This can be CLEARLY optimized
def anonymization_paragraph_batch_create_update(
    paragraphs_in: list[AnonymizationParagraphCreate], session: Session
) -> list[AnonymizationParagraph]:
    """
    Creates or updates a batch of paragraph records.

    Args:
        paragraphs_in (list[AnonymizationParagraphCreate]): Paragraph payloads.
        session (Session): Database session.

    Returns:
        list[AnonymizationParagraph]: Persisted paragraph records.
    """
    paragraphs = []

    for p_in in paragraphs_in:
        paragraph_id = text_to_uuid(p_in.text)

        paragraph = session.get(AnonymizationParagraph, paragraph_id)
        if paragraph:
            payload = _normalize_paragraph_payload(p_in.model_dump())
            payload.pop("id", None)
            for field, value in payload.items():
                if value is not None:
                    setattr(paragraph, field, value)

        else:
            payload = _normalize_paragraph_payload(p_in.model_dump())
            paragraph = AnonymizationParagraph(**payload)

        session.add(paragraph)
        session.commit()
        session.refresh(paragraph)

        paragraphs.append(paragraph)

    # refresh models (Must be a list or for-loop)
    [session.refresh(paragraph) for paragraph in paragraphs]

    return paragraphs

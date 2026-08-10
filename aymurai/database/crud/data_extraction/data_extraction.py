import uuid
from typing import Any

from sqlmodel import Session

from aymurai.database.schema import DataExtraction


def data_extraction_get(
    data_extraction_id: uuid.UUID,
    session: Session,
) -> DataExtraction | None:
    """
    Get a data-extraction record by ID.

    Args:
        data_extraction_id (uuid.UUID): ID of the data-extraction record.
        session (Session): SQLAlchemy session.

    Returns:
        DataExtraction | None: Data-extraction record if found, else None.
    """
    return session.get(DataExtraction, data_extraction_id)


def data_extraction_create_or_update(
    data_extraction_id: uuid.UUID,
    document: list[str],
    prediction: dict[str, Any],
    config: dict[str, Any],
    session: Session,
) -> DataExtraction:
    """
    Create or update a data-extraction record.

    Regenerating an extraction supersedes whatever was validated against the
    previous prediction, so `validation` is always reset to None here --
    mirroring `summarization_create_or_update`.

    Args:
        data_extraction_id (uuid.UUID): ID of the data-extraction record --
            matches the source Document's `document_id`.
        document (list[str]): Source document text that was extracted from.
        prediction (dict[str, Any]): LLM-produced DataExtractionResult (as a
            dict) -- destinatarios with ranked sector candidates, tema/subtema
            with their dropdown options, etc.
        config (dict[str, Any]): Generation config used for this run (model,
            search_backend, hybrid_weight, top_k, sector_mode, sector_top_k,
            nombre_origen_weight, max_retries, options).
        session (Session): SQLAlchemy session.

    Returns:
        DataExtraction: The created or updated DataExtraction record.
    """
    record = session.get(DataExtraction, data_extraction_id)

    if not record:
        record = DataExtraction(
            id=data_extraction_id,
            document=document,
            prediction=prediction,
            validation=None,
            config=config,
        )
    else:
        record.document = document
        record.prediction = prediction
        record.validation = None
        record.config = config

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def data_extraction_set_validation(
    data_extraction_id: uuid.UUID,
    validation: dict[str, Any],
    session: Session,
) -> DataExtraction | None:
    """
    Set the human-validated result on an existing data-extraction record.

    Args:
        data_extraction_id (uuid.UUID): ID of the data-extraction record --
            matches the source Document's `document_id`.
        validation (dict[str, Any]): Human-corrected DataExtractionResult (as
            a dict).
        session (Session): SQLAlchemy session.

    Returns:
        DataExtraction | None: The updated record, or None if no record
        exists for `data_extraction_id`.
    """
    record = session.get(DataExtraction, data_extraction_id)
    if not record:
        return None

    record.validation = validation

    session.add(record)
    session.commit()
    session.refresh(record)
    return record

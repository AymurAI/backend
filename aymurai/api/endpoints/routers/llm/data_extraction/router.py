from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID5
from sqlmodel import Session

from aymurai.database.crud.data_extraction.data_extraction import (
    data_extraction_set_validation,
)
from aymurai.database.crud.data_extraction.validated_destinatario import (
    validated_destinatario_create_or_update,
)
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import SuccessResponse

from . import organigram_matching
from .extraction_service import run_data_extraction
from .schemas import DataExtractionRequest, DataExtractionResult

logger = get_logger(__name__)

router = APIRouter()


@router.post("/data-extraction", response_model=DataExtractionResult)
async def extract_recommendation_data(
    payload: DataExtractionRequest,
    session: Session = Depends(get_session),
) -> DataExtractionResult:
    """
    Extract structured recommendation data (Defensoría del Pueblo) from an
    already-extracted document (see /misc/document-extract), cross-referencing
    each destinatario against the GCBA organigram so the frontend can present
    ranked candidates and let the user pick the right one.

    The result is persisted keyed by `payload.document.document_id`, so a
    later call to `/data-extraction/{document_id}/validate` can attach the
    human-reviewed corrections to it. If that `document_id` was already
    extracted before, the persisted result is returned directly by default
    (the LLM and organigram pipeline don't run again) -- pass
    `force_reextract=true` to re-run it anyway. See `run_data_extraction`.

    Args:
        payload (DataExtractionRequest): The document to process plus optional
            overrides (model, search_backend, hybrid_weight, top_k,
            sector_mode, sector_top_k, nombre_origen_weight, max_retries,
            options, force_reextract) -- see `DataExtractionRequest` for what
            each one does and its default.
        session (Session): SQLAlchemy session.

    Raises:
        HTTPException: 400 if `payload.document.document` is empty.

    Returns:
        DataExtractionResult: Extracted recommendation fields, with a ranked
        list of sector candidates per destinatario.
    """
    if not payload.document.document:
        raise HTTPException(
            status_code=400, detail="document.document cannot be empty."
        )

    return await run_data_extraction(
        payload.document,
        session,
        model=payload.model,
        search_backend=payload.search_backend,
        hybrid_weight=payload.hybrid_weight,
        top_k=payload.top_k,
        sector_mode=payload.sector_mode,
        sector_top_k=payload.sector_top_k,
        nombre_origen_weight=payload.nombre_origen_weight,
        max_retries=payload.max_retries,
        options=payload.options,
        force_reextract=payload.force_reextract,
    )


@router.put("/data-extraction/{document_id}/validate", response_model=SuccessResponse)
async def validate_recommendation_data(
    document_id: UUID5,
    payload: DataExtractionResult,
    session: Session = Depends(get_session),
) -> SuccessResponse:
    """
    Save a human-reviewed correction of a previously extracted result.

    For each GCBA destinatario with both `nombre` and `sector_confirmado`
    set, upserts a `ValidatedDestinatario` row keyed by the normalized
    nombre -- so the next time this same person is extracted, that sector is
    suggested first (see `extraction_service._validated_candidate`).

    Args:
        document_id (UUID5): ID of the document whose extraction is being
            validated -- must match a prior `/data-extraction` call's
            `payload.document.document_id`.
        payload (DataExtractionResult): The human-corrected extraction.
        session (Session): SQLAlchemy session.

    Raises:
        HTTPException: 404 if no extraction was ever saved for `document_id`.

    Returns:
        SuccessResponse: `id` is `document_id` on success.
    """
    record = data_extraction_set_validation(
        data_extraction_id=document_id,
        validation=payload.model_dump(),
        session=session,
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No data-extraction found for document_id={document_id}",
        )

    for destinatario in payload.destinatarios:
        if (
            organigram_matching.normalize_text(destinatario.sector) != "gcba"
            or not destinatario.nombre
            or not destinatario.sector_confirmado
        ):
            continue

        validated_destinatario_create_or_update(
            nombre_normalizado=organigram_matching.normalize_text(destinatario.nombre),
            nombre=destinatario.nombre,
            cargo=destinatario.cargo,
            sector=destinatario.sector_confirmado,
            session=session,
        )

    return SuccessResponse(id=document_id, msg="Validation saved")

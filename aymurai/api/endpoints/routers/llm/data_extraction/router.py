from __future__ import annotations

from fastapi import APIRouter, HTTPException

from aymurai.logger import get_logger

from .extraction_service import run_data_extraction
from .schemas import DataExtractionRequest, DataExtractionResult

logger = get_logger(__name__)

router = APIRouter()


@router.post("/data-extraction", response_model=DataExtractionResult)
async def extract_recommendation_data(
    payload: DataExtractionRequest,
) -> DataExtractionResult:
    """
    Extract structured recommendation data (Defensoría del Pueblo) from an
    already-extracted document (see /misc/document-extract), cross-referencing
    each destinatario against the GCBA organigram so the frontend can present
    ranked candidates and let the user pick the right one.

    Args:
        payload (DataExtractionRequest): The document to process plus optional
            overrides (model, search_backend, hybrid_weight, search_fields,
            top_k, max_retries, options) -- see `DataExtractionRequest` for
            what each one does and its default.

    Raises:
        HTTPException: 400 if `payload.document.document` is empty.

    Returns:
        DataExtractionResult: Extracted recommendation fields, with a ranked
        list of organigram candidates per destinatario.
    """
    if not payload.document.document:
        raise HTTPException(
            status_code=400, detail="document.document cannot be empty."
        )

    return await run_data_extraction(
        payload.document,
        model=payload.model,
        search_backend=payload.search_backend,
        hybrid_weight=payload.hybrid_weight,
        search_fields=payload.search_fields,
        top_k=payload.top_k,
        max_retries=payload.max_retries,
        options=payload.options,
    )

import uuid
from sqlmodel import Session, select, func
from sqlalchemy.orm import aliased

from aymurai.database.schema import (
    Prediction,
    Model,
    Paragraph,
    PredictionPublic,
    ModelType,
)
from aymurai.database.meta.extra import (
    ParagraphPredictionPublic,
)
from aymurai.database.utils import text_to_hash


def read_validation(
    text: str,
    model_name: str,
    session: Session,
) -> Prediction | None:
    """
    Read the validation labels for a given input hash.

    Args:
        input_hash (str): The hash of the input text.
        model_name (str): The name of the model associated with the prediction.
        session (Session): Database session dependency.

    Returns:
        list[DocLabel] | None: A list of validation labels for the given input hash, or None if no validation exists.
    """

    input_hash = text_to_hash(text)

    statement = (
        select(Prediction)
        .join(Model, Prediction.fk_model == Model.id)
        .where(
            Prediction.input_hash == input_hash,
            Model.name == model_name,
            Prediction.validation.isnot(None),
        )
        .order_by(Prediction.updated_at.desc(), Prediction.created_at.desc())
    )
    pred = session.exec(statement).first()

    return pred or None


def read_prediction_by_text(
    text: str,
    model_id: uuid.UUID,
    session: Session,
) -> Prediction | None:
    """
    Read the validation labels for a given input hash.

    Args:
        input_hash (str): The hash of the input text.
        model_name (str): The name of the model associated with the prediction.
        session (Session): Database session dependency.

    Returns:
        list[DocLabel] | None: A list of validation labels for the given input hash, or None if no validation exists.
    """

    input_hash = text_to_hash(text)

    statement = (
        select(Prediction)
        .where(
            Prediction.input_hash == input_hash,
            Prediction.fk_model == model_id,
            # Prediction.prediction.isnot(None),
        )
        .order_by(Prediction.updated_at.desc(), Prediction.created_at.desc())
    )
    pred = session.exec(statement).first()

    return pred or None


def get_paragraph_prediction_public(
    paragraph_pred: tuple[Paragraph, PredictionPublic | None],
) -> ParagraphPredictionPublic:
    paragraph, pred = paragraph_pred

    if pred is None:
        return ParagraphPredictionPublic(**paragraph.model_dump(), prediction=None)

    obj = ParagraphPredictionPublic(
        **paragraph.model_dump(),
        prediction=PredictionPublic(
            **pred.model_dump(),
            model=pred.model.model_dump(),
        ),
    )

    return obj


def read_document_prediction_paragraphs(
    document_id: uuid.UUID,
    model_type: ModelType,
    session: Session,
) -> list[ParagraphPredictionPublic]:
    """
    For each paragraph in `document_id` (ordered by Paragraph.index)
    and for the given `model_type`, return the most‐recent Prediction or None.
    """

    # 1) build a row_number window over each paragraph
    rn = (
        func.row_number()
        .over(
            partition_by=Prediction.fk_paragraph,
            order_by=(Prediction.updated_at.desc(), Prediction.created_at.desc()),
        )
        .label("rn")
    )

    # 2) subquery: join to Model by type & compute rn
    pred_subq = (
        select(Prediction, rn)
        .join(Model, Prediction.fk_model == Model.id)
        .where(Model.type == model_type)
    ).subquery()

    # alias the subquery as a full ORM-mapped Prediction
    LatestPred = aliased(Prediction, pred_subq)

    # 3) outer-join Paragraph → the aliased Prediction, filter rn==1, order by paragraph.index
    stmt = (
        select(Paragraph, LatestPred)
        .join(
            LatestPred,
            Paragraph.id == LatestPred.fk_paragraph,
            isouter=True,
        )
        .where(Paragraph.fk_document == document_id)
        .where((pred_subq.c.rn == 1) | (pred_subq.c.rn.is_(None)))
        .order_by(Paragraph.index)
    )

    rows = session.exec(stmt).all()
    # rows is list of (Paragraph, LatestPred or None)

    return [get_paragraph_prediction_public(row) for row in rows]

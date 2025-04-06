import uuid
from sqlmodel import Session, select
from aymurai.database.schema import Prediction

from aymurai.database.utils import text_to_hash
from aymurai.database.schema import Model


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


def read_prediction(
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

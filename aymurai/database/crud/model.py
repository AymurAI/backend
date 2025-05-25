from sqlmodel import Session, desc, select

from aymurai.database.schema import Model, ModelCreate, ModelPublic, ModelType
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger

logger = get_logger(__name__)


def register_model(
    model_name: str,
    app_version: str,
    model_type: ModelType,
    pipeline_path: str,
    session: Session,
) -> ModelPublic:
    """
    Register a model in the database.
    """
    model_id = text_to_uuid(f"{model_type}-{model_name}-{app_version}")

    # Check if the model already exists
    model = session.get(Model, model_id)
    if model:
        logger.warning(f"Model already exists: {model_id}. skipping creation.")
        return ModelPublic(**model.model_dump())

    model = ModelCreate(
        id=model_id,
        name=model_name,
        version=app_version,
        type=model_type,
        pipeline_path=pipeline_path,
    ).compile()

    session.add(model)
    session.commit()
    session.refresh(model)

    return ModelPublic(**model.model_dump())


def read_latest_model_by_type(model_type: ModelType, session: Session) -> ModelPublic:
    """
    Read a model from the database by its type.
    """
    stm = select(Model).where(Model.type == model_type).order_by(desc(Model.created_at))
    model = session.exec(stm).first()

    if not model:
        raise ValueError(f"Model not found for type: {model_type}")

    return ModelPublic(**model.model_dump())

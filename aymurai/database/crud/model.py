from sqlmodel import Session
from aymurai.database.schema import Model, ModelPublic, ModelCreate
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger


logger = get_logger(__name__)


def register_model(model_name: str, app_version: str, session: Session) -> ModelPublic:
    """
    Register a model in the database.
    """
    model_id = text_to_uuid(f"{model_name}-{app_version}")

    # Check if the model already exists
    model = session.get(Model, model_id)
    if model:
        logger.warning(f"Model already exists: {model_id}. skipping creation.")
        return ModelPublic(**model.model_dump())

    model = ModelCreate(name=model_name, version=app_version).compile()

    session.add(model)
    session.commit()
    session.refresh(model)

    return ModelPublic(**model.model_dump())

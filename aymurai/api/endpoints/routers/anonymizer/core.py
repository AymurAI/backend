import os
from functools import cache

from fastapi import Depends
from sqlmodel import Session

from aymurai.api.utils import load_pipeline
from aymurai.database.crud.model import register_model
from aymurai.database.schema import Model
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.pipeline.pipeline import AymurAIPipeline
from aymurai.settings import settings

logger = get_logger(__name__)

RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH


@cache
def get_anonimization_model(session: Session = Depends(get_session)) -> Model:
    """
    Get the model from the database.

    Args:
        session (Session): Database session dependency.

    Returns:
        Model: The model from the database.
    """
    return register_model(
        model_name="flair-anonymizer",
        app_version=settings.APP_VERSION,
        session=session,
    )


@cache
def get_datapublic_model(session: Session = Depends(get_session)) -> Model:
    """
    Get the model from the database.

    Args:
        session (Session): Database session dependency.

    Returns:
        Model: The model from the database.
    """
    return register_model(
        model_name="datapublic",
        app_version=settings.APP_VERSION,
        session=session,
    )


@cache
def load_anonymization_pipeline() -> AymurAIPipeline:
    return load_pipeline(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )


@cache
def load_datapublic_pipeline() -> AymurAIPipeline:
    return load_pipeline(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "full-paragraph")
    )

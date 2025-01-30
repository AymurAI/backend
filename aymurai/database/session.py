from typing import Generator

from sqlmodel import Session, create_engine

from aymurai.settings import settings


def get_engine(echo: bool = False):
    return create_engine(
        str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True, echo=echo
    )


def get_session(echo: bool = False) -> Generator:
    engine = get_engine(echo=echo)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

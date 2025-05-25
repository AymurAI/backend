import logging
import os

from sqlmodel import select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from aymurai.database.session import get_session
from aymurai.settings import settings

logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def check_db_connection():
    logger.info(f"Checking database connection to {settings.SQLALCHEMY_DATABASE_URI}")

    if (db_uri := str(settings.SQLALCHEMY_DATABASE_URI)).startswith("sqlite"):
        db_file = db_uri.replace("sqlite:///", "")
        if not os.path.exists(db_file):
            logger.info(f"Creating SQLite database at {db_file}")
            os.makedirs(os.path.dirname(db_file), exist_ok=True)

    try:
        session = next(get_session())
        session.exec(select(1))

    except Exception as e:
        logger.error(e)
        raise e

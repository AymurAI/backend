import os
import logging

from rich.logging import RichHandler

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_LEVEL_MAP = {
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=LOG_LEVEL_MAP[LOG_LEVEL],
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True)],
    )

    logger = logging.getLogger(name)
    return logger

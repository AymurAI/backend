import os
import logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_LEVEL_MAP = {
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=LOG_LEVEL_MAP[LOG_LEVEL],
        format="%(levelname)s:%(name)s:%(message)s",
        datefmt="[%X]",
    )

    logger = logging.getLogger(name)
    return logger

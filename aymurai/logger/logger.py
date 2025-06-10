import os
import logging

from rich.logging import RichHandler

LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


class PrefixFilter(logging.Filter):
    def __init__(self, prefix: str):
        super().__init__()
        self.prefix = prefix

    def filter(self, record: logging.LogRecord) -> bool:
        # Adding a custom prefix to the log message
        record.msg = f"{self.prefix} {record.msg}"
        return True


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=LOG_LEVEL_MAP[LOG_LEVEL],
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True)],
    )

    return logging.getLogger(name)

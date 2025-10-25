import logging
from logging import Logger

from .config import get_settings


def configure_logging() -> Logger:
    """تهيئة مسجل موحد لتطبيق FastAPI."""
    settings = get_settings()

    logger = logging.getLogger(settings.app_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger

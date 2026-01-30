"""Structured logging for pub-sub events (publish, subscribe, deliver)."""

import logging
import sys
from typing import Any, Optional


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger for observability."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger

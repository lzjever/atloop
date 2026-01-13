"""Logging configuration for CLI."""

import logging
import os
import sys
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Setup logging configuration for CLI.

    Log level is determined by (in priority order):
    1. log_level parameter (if provided)
    2. ATLOOP_LOG_LEVEL environment variable
    3. Default: WARNING

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   If None, reads from ATLOOP_LOG_LEVEL environment variable.
    """
    # Determine log level
    if log_level is None:
        log_level = os.getenv("ATLOOP_LOG_LEVEL", "WARNING").upper()

    # Convert string to logging level
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        # Invalid log level, default to INFO
        print(
            f"Warning: Invalid log level '{log_level}', using INFO instead.",
            file=sys.stderr,
        )
        numeric_level = logging.INFO

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric_level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Set atloop logger level
    logging.getLogger("atloop").setLevel(numeric_level)

    # Suppress noisy third-party loggers unless DEBUG
    if numeric_level > logging.DEBUG:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

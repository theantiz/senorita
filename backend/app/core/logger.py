import logging
import os
import sys


def setup_logger(name: str = "senorita") -> logging.Logger:
    """Configures and returns a centralized logger for the application."""
    logger = logging.getLogger(name)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    # Only configure if no handlers are present to avoid duplicate logs
    if not logger.handlers:
        # Create console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Standard format
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(level)

    return logger


# Create default instance
logger = setup_logger()

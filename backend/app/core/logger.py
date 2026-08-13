import logging
import sys


def setup_logger(name: str = "senorita") -> logging.Logger:
    """Configures and returns a centralized logger for the application."""
    logger = logging.getLogger(name)

    # Only configure if no handlers are present to avoid duplicate logs
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Create console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Standard format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger

# Create default instance
logger = setup_logger()

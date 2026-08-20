# Backwards-compatibility shim — import from here as before:
#   from app.core.logger import logger
# New code should prefer:
#   from app.core.logging import get_logger
from app.core.logging import get_logger, logger  # noqa: F401

__all__ = ["logger", "get_logger"]

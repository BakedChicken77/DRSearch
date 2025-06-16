import logging
from .config import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger("agentic_drsearch_backend")

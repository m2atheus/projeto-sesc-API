import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("weather")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False


def log(event: str, *, level: int = logging.INFO, **details: object) -> None:
    logger.log(level, json.dumps({"at": datetime.now(UTC).isoformat(), "event": event, **details},
                                 ensure_ascii=True, default=str))

import json
import logging
from contextvars import ContextVar
from uuid import uuid4

request_id: ContextVar[str] = ContextVar("request_id", default="")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log(event: str, **fields: object) -> None:
    payload = {"event": event, "request_id": request_id.get(), **fields}
    logging.getLogger("ticketing").info(json.dumps(payload, default=str, sort_keys=True))


def new_request_id() -> str:
    return str(uuid4())

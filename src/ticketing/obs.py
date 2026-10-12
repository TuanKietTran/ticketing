import json
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from uuid import uuid4

request_id: ContextVar[str] = ContextVar("request_id", default="")


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log(event: str, **fields: object) -> None:
    payload = {"event": event, "request_id": request_id.get(), **fields}
    logging.getLogger("ticketing").info(json.dumps(payload, default=str, sort_keys=True))


def timed(fn: Callable[..., object]) -> Callable[..., object]:
    start = time.monotonic()
    result = fn()
    log("operation", elapsed_ms=(time.monotonic() - start) * 1000)
    return result


def new_request_id() -> str:
    return str(uuid4())

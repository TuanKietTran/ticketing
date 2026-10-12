import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


class IdempotencyMiddleware:
    """Persist mutating HTTP responses before releasing the idempotency claim."""

    def __init__(self, app: ASGIApp, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.app = app
        self.sessions = sessions

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") in {"GET", "HEAD", "OPTIONS"}
            or scope.get("path", "").startswith("/webhooks/")
        ):
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        key = request.headers.get("idempotency-key")
        if not key:
            response = JSONResponse({"code": "missing_idempotency_key"}, status_code=422)
            await response(scope, receive, send)
            return
        body = await request.body()
        request._receive = _replay_body(body)
        default_actor = request.client.host if request.client else "anonymous"
        actor = request.headers.get("x-actor-id", default_actor)
        digest = hashlib.sha256(body).hexdigest()
        async with self.sessions() as session:
            async with session.begin():
                inserted = await session.execute(
                    text(
                        "INSERT INTO idempotency_keys(actor_id,key,request_hash,expires_at) "
                        "VALUES (:actor,:key,:hash,:expires) ON CONFLICT (actor_id,key) DO NOTHING"
                    ),
                    {
                        "actor": actor,
                        "key": key,
                        "hash": digest,
                        "expires": datetime.now(UTC) + timedelta(hours=24),
                    },
                )
                if inserted.rowcount == 0:
                    stored = (
                        await session.execute(
                            text(
                                "SELECT request_hash,status_code,response_json "
                                "FROM idempotency_keys "
                                "WHERE actor_id=:actor AND key=:key AND expires_at > now()"
                            ),
                            {"actor": actor, "key": key},
                        )
                    ).mappings().first()
                    if stored is None:
                        await session.execute(
                            text("DELETE FROM idempotency_keys WHERE actor_id=:actor AND key=:key"),
                            {"actor": actor, "key": key},
                        )
                    elif stored["request_hash"] != digest:
                        response = JSONResponse(
                            {"code": "idempotency_body_mismatch"}, status_code=422
                        )
                        await response(scope, receive, send)
                        return
                    elif stored["status_code"] is None:
                        response = JSONResponse(
                            {"code": "idempotency_in_flight"},
                            status_code=409,
                            headers={"Retry-After": "1"},
                        )
                        await response(scope, receive, send)
                        return
                    else:
                        response = JSONResponse(
                            stored["response_json"], status_code=stored["status_code"]
                        )
                        await response(scope, receive, send)
                        return
                captured = CaptureSend()
                await self.app(scope, request.receive, captured)
                payload = _json_or_text(captured.body)
                await session.execute(
                    text(
                        "UPDATE idempotency_keys SET status_code=:status,"
                        "response_json=CAST(:body AS jsonb) "
                        "WHERE actor_id=:actor AND key=:key"
                    ),
                    {
                        "actor": actor,
                        "key": key,
                        "status": captured.status,
                        "body": json.dumps(payload),
                    },
                )
                await captured.send(scope, receive, send)


class CaptureSend:
    def __init__(self) -> None:
        self.status = 500
        self.headers: list[tuple[bytes, bytes]] = []
        self.body = b""

    async def __call__(self, message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = message.get("headers", [])
        elif message["type"] == "http.response.body":
            self.body += message.get("body", b"")

    async def send(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": self.status, "headers": self.headers})
        await send({"type": "http.response.body", "body": self.body})


def _json_or_text(body: bytes) -> object:
    try:
        return json.loads(body or b"null")
    except json.JSONDecodeError:
        return {"raw": body.decode(errors="replace")}


def _replay_body(body: bytes) -> Callable[[], Awaitable[dict[str, object]]]:
    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive

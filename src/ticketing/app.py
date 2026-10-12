import asyncio
import json
import random
import time
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ticketing.api.idempotency import IdempotencyMiddleware
from ticketing.auth import authenticate_organizer, hash_api_key
from ticketing.clock import SystemClock
from ticketing.db import make_engine, make_session_factory
from ticketing.db.redis import make_redis
from ticketing.deadletter import (
    discard_dead_letter,
    list_dead_letters,
    replay_dead_letter,
)
from ticketing.inventory import Inventory, claim_general_admission
from ticketing.obs import configure_logging, log, new_request_id, request_id
from ticketing.orders import OrderState, checkout_hold, new_order, transition_order
from ticketing.payments import MockPSP, receive_webhook, record_charge
from ticketing.refunds import refund_order
from ticketing.tickets import TicketService, issue_ticket_set, scan_ticket
from ticketing.waitingroom import WaitingRoom


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="ticketing", version="0.1.0")
    sessions = make_session_factory(make_engine())
    app.add_middleware(IdempotencyMiddleware, sessions=sessions)
    app.state.accepting = True
    metrics_state = {"requests": 0, "inflight": 0, "errors": 0}
    duration_buckets = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)
    duration_histograms: dict[str, dict[str, object]] = {}

    def endpoint_name(request: Request) -> str:
        path = request.url.path
        if request.method == "GET" and path.startswith("/events/"):
            return "browse"
        if path.endswith("/holds"):
            return "hold"
        if path.endswith("/checkout"):
            return "checkout"
        if path.endswith("/pay"):
            return "pay"
        return "other"

    def record_duration(endpoint: str, elapsed_seconds: float) -> None:
        histogram = duration_histograms.setdefault(
            endpoint, {"count": 0, "sum": 0.0, "buckets": [0] * len(duration_buckets)}
        )
        histogram["count"] = int(histogram["count"]) + 1
        histogram["sum"] = float(histogram["sum"]) + elapsed_seconds
        buckets = histogram["buckets"]
        assert isinstance(buckets, list)
        for index, bound in enumerate(duration_buckets):
            if elapsed_seconds <= bound:
                buckets[index] += 1

    inventory = Inventory()
    psp = MockPSP()
    ticket_service = TicketService("development-only-change-me")
    clock = SystemClock()
    holds: dict[UUID, object] = {}
    orders: dict[UUID, object] = {}
    event_sections: dict[UUID, UUID] = {}
    webhook_events: set[str] = set()
    waiting_room = WaitingRoom()
    redis = make_redis()

    async def require_admin(x_api_key: str = Header(..., alias="X-API-Key")) -> UUID:
        async with sessions() as session:
            organizer_id = await authenticate_organizer(session, x_api_key)
        if organizer_id is None:
            raise HTTPException(status_code=403, detail="invalid organizer key")
        return organizer_id

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or new_request_id()
        started = time.perf_counter()
        endpoint = endpoint_name(request)
        token = request_id.set(rid)
        metrics_state["requests"] += 1
        metrics_state["inflight"] += 1
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        except Exception as exc:
            metrics_state["errors"] += 1
            log("request_error", error=str(exc), path=request.url.path)
            return JSONResponse(
                status_code=500,
                content={"code": "internal_error", "request_id": rid},
            )
        finally:
            metrics_state["inflight"] -= 1
            record_duration(endpoint, time.perf_counter() - started)
            request_id.reset(token)

    class InventoryRequest(BaseModel):
        capacity: int = Field(ge=0)

    class HoldRequest(BaseModel):
        buyer_id: UUID
        quantity: int = Field(gt=0)

    class RefundRequest(BaseModel):
        amount_minor: int = Field(gt=0)
        quantity: int = Field(gt=0)

    @app.post("/admin/events/{event_id}/inventory")
    async def seed_inventory(event_id: UUID, payload: InventoryRequest) -> dict[str, object]:
        now = clock.now()
        organizer_id, section_id = uuid4(), uuid4()
        async with sessions() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "INSERT INTO organizers(id,name,api_key_hash) "
                        "VALUES (:id,'default',:key_hash)"
                    ),
                    {"id": organizer_id, "key_hash": hash_api_key("development-admin")},
                )
                await session.execute(
                    text(
                        "INSERT INTO events(id,organizer_id,name,sale_opens_at,sale_closes_at) "
                        "VALUES (:id,:org,'event',:open,:close)"
                    ),
                    {
                        "id": event_id,
                        "org": organizer_id,
                        "open": now - timedelta(minutes=1),
                        "close": now + timedelta(days=1),
                    },
                )
                await session.execute(
                    text(
                        "INSERT INTO sections(id,event_id,name,mode,capacity) "
                        "VALUES (:id,:event,'GA','general_admission',:capacity)"
                    ),
                    {"id": section_id, "event": event_id, "capacity": payload.capacity},
                )
        event_sections[event_id] = section_id
        inventory.add_section(event_id, payload.capacity)
        catalog = {
            "event_id": str(event_id),
            "capacity": payload.capacity,
            "mode": "general_admission",
        }
        await redis.set(f"event:{event_id}:catalog", json.dumps(catalog), ex=300)
        return catalog

    @app.get("/events/{event_id}")
    async def browse_event(event_id: UUID) -> dict[str, object]:
        cached = await redis.get(f"event:{event_id}:catalog")
        if cached:
            return json.loads(cached)
        async with sessions() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT e.id, s.capacity, s.mode FROM events e "
                        "JOIN sections s ON s.event_id=e.id WHERE e.id=:event LIMIT 1"
                    ),
                    {"event": event_id},
                )
            ).mappings().first()
        if row is None:
            raise HTTPException(status_code=404, detail="event not found")
        catalog = {
            "event_id": str(row["id"]),
            "capacity": row["capacity"],
            "mode": row["mode"],
        }
        await redis.set(f"event:{event_id}:catalog", json.dumps(catalog), ex=300)
        return catalog

    @app.post("/events/{event_id}/holds", status_code=201)
    async def create_hold(
        event_id: UUID,
        payload: HoldRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ) -> dict[str, object]:
        section_id = event_sections.get(event_id)
        expires_at = clock.now() + timedelta(minutes=10)
        hold_id = None
        for attempt in range(4):
            try:
                async with sessions() as session:
                    async with session.begin():
                        if section_id is None:
                            section_id = (
                                await session.execute(
                                    text("SELECT id FROM sections WHERE event_id=:event LIMIT 1"),
                                    {"event": event_id},
                                )
                            ).scalar_one_or_none()
                        if section_id is None:
                            raise HTTPException(status_code=404, detail="event not found")
                        hold_id = await claim_general_admission(
                            session,
                            event_id,
                            section_id,
                            payload.buyer_id,
                            idempotency_key,
                            payload.quantity,
                            expires_at,
                        )
                break
            except DBAPIError as exc:
                if attempt == 3:
                    raise HTTPException(status_code=503, detail="inventory busy") from exc
                await asyncio.sleep(random.uniform(0.01, 0.1) * (attempt + 1))
        if hold_id is None:
            raise HTTPException(status_code=409, detail="inventory unavailable")
        return {"hold_id": str(hold_id), "expires_at": expires_at.isoformat()}

    @app.post("/holds/{hold_id}/checkout", status_code=201)
    async def checkout(
        hold_id: UUID, idempotency_key: str = Header(..., alias="Idempotency-Key")
    ) -> dict[str, object]:
        if hold_id in holds:
            hold = holds[hold_id]
            quantity = inventory.checkout(hold_id, clock.now())
            order = new_order(hold.buyer_id, quantity)  # type: ignore[attr-defined]
            order.transition(OrderState.AWAITING_PAYMENT, "hold checkout")
            orders[order.id] = order
            return {"order_id": str(order.id), "state": order.state}
        async with sessions() as session:
            async with session.begin():
                order_id = await checkout_hold(session, hold_id, clock.now())
        return {"order_id": str(order_id), "state": OrderState.AWAITING_PAYMENT}

    @app.post("/orders/{order_id}/pay")
    async def pay(
        order_id: UUID, idempotency_key: str = Header(..., alias="Idempotency-Key")
    ) -> dict[str, object]:
        order = orders.get(order_id)
        if order is not None:
            charge = await psp.charge(order_id, order.quantity * 100)  # type: ignore[attr-defined]
            if order.state is OrderState.AWAITING_PAYMENT:  # type: ignore[attr-defined]
                order.transition(OrderState.PAID, "charge succeeded")  # type: ignore[attr-defined]
                ticket_service.issue_once(order_id, order.quantity)  # type: ignore[attr-defined]
            return {"order_id": str(order_id), "state": order.state, "charge_id": charge.id}
        async with sessions() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        text("SELECT total_minor,currency FROM orders WHERE id=:id"),
                        {"id": order_id},
                    )
                ).mappings().first()
                if row is None:
                    raise HTTPException(status_code=404, detail="order not found")
                charge = await psp.charge(order_id, row["total_minor"])
                await record_charge(
                    session, order_id, row["total_minor"], row["currency"], charge.id
                )
                tickets = await issue_ticket_set(
                    session, order_id, 1, "development-only-change-me"
                )
                await transition_order(session, order_id, OrderState.TICKETED, "tickets issued")
        return {
            "order_id": str(order_id),
            "state": OrderState.TICKETED,
            "charge_id": charge.id,
            "tickets": len(tickets),
        }

    @app.post("/orders/{order_id}/refunds")
    async def refund(order_id: UUID, payload: RefundRequest) -> dict[str, str]:
        async with sessions() as session:
            async with session.begin():
                refund_id = await refund_order(
                    session, order_id, payload.amount_minor, payload.quantity
                )
        return {"refund_id": str(refund_id), "order_id": str(order_id)}

    @app.post("/tickets/{ticket_id}/scan")
    async def scan(ticket_id: UUID, device_id: str = "online") -> dict[str, bool]:
        async with sessions() as session:
            async with session.begin():
                accepted = await scan_ticket(session, ticket_id, device_id)
        return {"accepted": accepted}

    @app.post("/webhooks/mock")
    async def mock_webhook(
        request: Request,
        x_signature: str = Header(...),
        x_timestamp: str = Header(...),
        x_event_id: str = Header(...),
    ) -> dict[str, str]:
        raw = await request.body()
        if not psp.verify(raw.decode(), x_signature, x_timestamp, int(time.time())):
            raise HTTPException(status_code=400, detail="invalid webhook signature")
        async with sessions() as session:
            async with session.begin():
                try:
                    status = await receive_webhook(
                        session, psp, x_event_id, raw.decode(), x_signature, x_timestamp
                    )
                except (ValueError, KeyError) as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
        webhook_events.add(x_event_id)
        return {"status": status}

    @app.get("/admin/dead-letters")
    async def list_dead_letters_endpoint(
        _organizer_id: UUID = Depends(require_admin),
    ) -> list[dict[str, object]]:
        async with sessions() as session:
            async with session.begin():
                return await list_dead_letters(session)

    @app.get("/admin/dead-letters/{item_id}")
    async def inspect_dead_letter(
        item_id: UUID, _organizer_id: UUID = Depends(require_admin)
    ) -> dict[str, object]:
        async with sessions() as session:
            async with session.begin():
                rows = await list_dead_letters(session, limit=1000)
        for row in rows:
            if row["id"] == item_id:
                return row
        raise HTTPException(status_code=404, detail="dead letter not found")

    @app.post("/admin/dead-letters/{item_id}/replay")
    async def replay_dead_letter_endpoint(
        item_id: UUID, _organizer_id: UUID = Depends(require_admin)
    ) -> dict[str, str]:
        async with sessions() as session:
            async with session.begin():
                if not await replay_dead_letter(session, item_id):
                    raise HTTPException(status_code=404, detail="dead letter unavailable")
        return {"status": "replayed"}

    @app.post("/admin/dead-letters/{item_id}/discard")
    async def discard_dead_letter_endpoint(
        item_id: UUID,
        reason: str = "operator discard",
        _organizer_id: UUID = Depends(require_admin),
    ) -> dict[str, str]:
        async with sessions() as session:
            async with session.begin():
                if not await discard_dead_letter(session, item_id, reason):
                    raise HTTPException(status_code=404, detail="dead letter unavailable")
        return {"status": "discarded"}

    @app.post("/waiting-room/{event_id}/admit")
    async def admit_waiting_room(event_id: UUID, count: int = 1) -> list[dict[str, str]]:
        del event_id
        return [{"token": str(admission.token)} for admission in waiting_room.admit(count)]

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        if not app.state.accepting:
            raise HTTPException(status_code=503, detail="draining")
        try:
            async with sessions() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"status": "ok"}

    @app.on_event("shutdown")
    async def graceful_shutdown() -> None:
        app.state.accepting = False

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        lines = [
            "# TYPE ticketing_up gauge",
            "ticketing_up 1",
            "# TYPE ticketing_requests_total counter",
            f"ticketing_requests_total {metrics_state['requests']}",
            "# TYPE ticketing_inflight gauge",
            f"ticketing_inflight {metrics_state['inflight']}",
            "# TYPE ticketing_errors_total counter",
            f"ticketing_errors_total {metrics_state['errors']}",
            "# TYPE ticketing_request_duration_seconds histogram",
        ]
        for endpoint, histogram in duration_histograms.items():
            buckets = histogram["buckets"]
            assert isinstance(buckets, list)
            for bound, count in zip(duration_buckets, buckets, strict=False):
                lines.append(
                    "ticketing_request_duration_seconds_bucket{"
                    f'endpoint="{endpoint}",le="{bound}"}} {count}'
                )
            lines.append(
                f'ticketing_request_duration_seconds_bucket{{endpoint="{endpoint}",le="+Inf"}} '
                f'{histogram["count"]}'
            )
            lines.append(
                f'ticketing_request_duration_seconds_sum{{endpoint="{endpoint}"}} '
                f'{histogram["sum"]}'
            )
            lines.append(
                f'ticketing_request_duration_seconds_count{{endpoint="{endpoint}"}} '
                f'{histogram["count"]}'
            )
        return "\n".join(lines) + "\n"

    return app


app = create_app()

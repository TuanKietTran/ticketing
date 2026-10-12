import time
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ticketing.clock import SystemClock
from ticketing.inventory import Inventory, SoldOut
from ticketing.obs import configure_logging, new_request_id, request_id
from ticketing.orders import IdempotencyStore, OrderState, new_order
from ticketing.orders.service import IdempotencyResult
from ticketing.payments import MockPSP
from ticketing.tickets import TicketService


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="ticketing", version="0.1.0")
    inventory = Inventory()
    idempotency = IdempotencyStore()
    psp = MockPSP()
    ticket_service = TicketService("development-only-change-me")
    clock = SystemClock()
    holds: dict[UUID, object] = {}
    orders: dict[UUID, object] = {}
    webhook_events: set[str] = set()

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or new_request_id()
        token = request_id.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"code": "internal_error", "request_id": rid},
            )
        finally:
            request_id.reset(token)

    class InventoryRequest(BaseModel):
        capacity: int = Field(ge=0)

    class HoldRequest(BaseModel):
        buyer_id: UUID
        quantity: int = Field(gt=0)

    @app.post("/admin/events/{event_id}/inventory")
    async def seed_inventory(event_id: UUID, payload: InventoryRequest) -> dict[str, object]:
        inventory.add_section(event_id, payload.capacity)
        return {"event_id": str(event_id), "capacity": payload.capacity}

    @app.post("/events/{event_id}/holds", status_code=201)
    async def create_hold(
        event_id: UUID,
        payload: HoldRequest,
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ) -> dict[str, object]:
        def execute() -> object:
            try:
                hold = inventory.hold(event_id, payload.buyer_id, payload.quantity, clock.now())
            except (SoldOut, KeyError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            holds[hold.id] = hold
            body = {"hold_id": str(hold.id), "expires_at": hold.expires_at.isoformat()}
            return IdempotencyResult(201, body)

        result = idempotency.execute(
            str(payload.buyer_id), idempotency_key, payload.model_dump_json().encode(), execute
        )
        return result.body  # type: ignore[no-any-return]

    @app.post("/holds/{hold_id}/checkout", status_code=201)
    async def checkout(
        hold_id: UUID, idempotency_key: str = Header(..., alias="Idempotency-Key")
    ) -> dict[str, object]:
        hold = holds.get(hold_id)
        if hold is None:
            raise HTTPException(status_code=404, detail="hold not found")
        quantity = inventory.checkout(hold_id, clock.now())
        order = new_order(hold.buyer_id, quantity)  # type: ignore[attr-defined]
        order.transition(OrderState.AWAITING_PAYMENT, "hold checkout")
        orders[order.id] = order
        return {"order_id": str(order.id), "state": order.state}

    @app.post("/orders/{order_id}/pay")
    async def pay(
        order_id: UUID, idempotency_key: str = Header(..., alias="Idempotency-Key")
    ) -> dict[str, object]:
        order = orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        charge = await psp.charge(order_id, order.quantity * 100)  # type: ignore[attr-defined]
        if order.state is OrderState.AWAITING_PAYMENT:  # type: ignore[attr-defined]
            order.transition(OrderState.PAID, "charge succeeded")  # type: ignore[attr-defined]
            ticket_service.issue_once(order_id, order.quantity)  # type: ignore[attr-defined]
        return {"order_id": str(order_id), "state": order.state, "charge_id": charge.id}

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
        if x_event_id in webhook_events:
            return {"status": "duplicate"}
        webhook_events.add(x_event_id)
        return {"status": "accepted"}

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> str:
        return "# TYPE ticketing_up gauge\nticketing_up 1\n"

    return app


app = create_app()

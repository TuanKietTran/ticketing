from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ticketing.obs import configure_logging, new_request_id, request_id


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="ticketing", version="0.1.0")

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

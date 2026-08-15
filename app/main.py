"""FastAPI app factory. No product-facing routes yet — those land starting Sprint 1-2
per the sprint plan; this sprint is scaffolding only (CLAUDE.md project structure §3)."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.config import get_settings
from app.logging_config import request_id_var, setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="BUSY Integration Platform")

    @app.middleware("http")
    async def add_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Reuse an incoming request ID (e.g. from a proxy) so a request can be traced
        # end-to-end; otherwise mint one. Threaded into every log line via request_id_var.
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

"""FastAPI app factory."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse

from app.api.v1 import (
    admin,
    auth,
    categories,
    material_centers,
    outbox,
    products,
    quotations,
    sales_people,
    sync,
)
from app.config import get_settings
from app.db.session import SessionLocal
from app.domain.catalog.scheduler import catalog_sync_loop
from app.logging_config import request_id_var, setup_logging
from app.outbox.worker import outbox_worker_loop

access_logger = logging.getLogger("app.access")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    stop_event = asyncio.Event()
    tasks: list[asyncio.Task[None]] = []

    if settings.catalog_sync_enabled:
        tasks.append(
            asyncio.create_task(
                catalog_sync_loop(
                    SessionLocal,
                    settings,
                    interval_seconds=settings.catalog_sync_interval_seconds,
                    stop_event=stop_event,
                )
            )
        )
    if settings.outbox_worker_enabled:
        tasks.append(
            asyncio.create_task(
                outbox_worker_loop(
                    SessionLocal,
                    settings,
                    interval_seconds=settings.outbox_worker_interval_seconds,
                    stop_event=stop_event,
                )
            )
        )

    try:
        yield
    finally:
        if tasks:
            stop_event.set()
            await asyncio.gather(*tasks)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="BUSY Integration Platform", lifespan=_lifespan)

    @app.middleware("http")
    async def add_request_id_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Reuse an incoming request ID (e.g. from a proxy) so a request can be traced
        # end-to-end; otherwise mint one. Threaded into every log line via request_id_var.
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        token = request_id_var.set(request_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            access_logger.exception(
                "%s %s failed after %.1fms", request.method, request.url.path, elapsed_ms
            )
            raise
        finally:
            request_id_var.reset(token)
        elapsed_ms = (time.monotonic() - start) * 1000
        access_logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/console", include_in_schema=False)
    async def console() -> FileResponse:
        # Dev-only manual test page (login + Sale Quotation create/list against this same
        # server, same-origin so no CORS is needed) — not part of the real product API.
        return FileResponse(Path(__file__).parent / "static" / "console.html")

    @app.get("/admin", include_in_schema=False)
    async def admin_dashboard() -> FileResponse:
        # Same idea as /console but for superadmin-only views (all users, all quotations
        # across every branch, sales-people management) — the API itself still enforces
        # SuperadminUser, this page is just the surface for it.
        return FileResponse(Path(__file__).parent / "static" / "admin.html")

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(products.router, prefix="/api/v1")
    app.include_router(categories.router, prefix="/api/v1")
    app.include_router(material_centers.router, prefix="/api/v1")
    app.include_router(sync.router, prefix="/api/v1")
    app.include_router(quotations.router, prefix="/api/v1")
    app.include_router(outbox.router, prefix="/api/v1")
    app.include_router(sales_people.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app


app = create_app()

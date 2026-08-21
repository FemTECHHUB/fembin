"""Entry point for cPanel's "Setup Python App" (Phusion Passenger).

Passenger expects a WSGI callable named `application` in this file — FastAPI/Starlette
are ASGI, not WSGI, so `a2wsgi.ASGIMiddleware` bridges the two. This is only needed for
the Passenger deployment path; local dev still runs the ASGI app directly via
`uv run uvicorn app.main:app` (see README).

Not used, and not needed, for any other deployment target (Docker, a VPS running uvicorn
directly, etc.) — those should import `app.main:app` as normal.
"""

from a2wsgi import ASGIMiddleware

from app.main import app as _asgi_app

# a2wsgi's type stubs describe a slightly different ASGI callable shape than
# Starlette/FastAPI's own — a stub mismatch, not a real bug (verified at runtime via
# httpx.WSGITransport against this exact object before this file was committed).
application = ASGIMiddleware(_asgi_app)  # type: ignore[arg-type]

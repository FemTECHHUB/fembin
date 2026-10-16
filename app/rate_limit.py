"""Shared slowapi `Limiter` instance.

Its own module, not defined in app/main.py or app/api/v1/auth.py: main.py attaches it to
`app.state` and registers the exception handler; auth.py's `@limiter.limit(...)` decorator
needs the same instance at import time, before `create_app()` ever runs. Either of those
two importing the other directly would be circular (CLAUDE.md §2.1 — one direction of
dependency), so both import this instead.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

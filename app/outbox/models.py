"""The durable queue every BUSY write goes through — no exceptions (CLAUDE.md §2.2).

BUSY is a single instance with no proven write concurrency; a request handler that posts
to it synchronously won't hold up under concurrent load. Every write is a row here first,
carrying an idempotency key, so a retried request never double-posts.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class OutboxStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class OutboxJob(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus, native_enum=False, length=16), default=OutboxStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(default=0)
    # The correctness requirement CLAUDE.md §2.2 calls out: before posting, check whether
    # this key already produced a result. Order code / Moniepoint merchantReference later;
    # caller-supplied for now.
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

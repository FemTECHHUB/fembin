"""Pydantic models for the outbox and Sale Quotation endpoints — separate from
app/api/v1/schemas.py (catalog) since this is a different, ad-hoc-added feature area."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.outbox.models import OutboxStatus


class QuotationItemIn(BaseModel):
    item_name: str
    unit_name: str
    qty: Decimal
    price: Decimal
    amount: Decimal


class QuotationCreateRequest(BaseModel):
    # Caller-supplied — e.g. a UUID or the caller's own quote reference. Retrying a
    # request with the same key returns the existing job instead of double-posting
    # (CLAUDE.md §2.2).
    idempotency_key: str
    vch_series_name: str = "Main"
    # e.g. "RCC" for the "Main" series — company-specific and not derivable from BUSY
    # (CLAUDE.md §8), so there's no safe default; the caller must know their own prefix.
    vch_no_prefix: str
    date: str  # DD-MM-YYYY
    sale_type_name: str
    customer_name: str
    # material_center_name is deliberately NOT a client-supplied field — it's derived from
    # the authenticated user's assigned material center (CLAUDE.md NFR6), not free-text
    # caller input. See app/api/v1/quotations.py.
    # Which named SalesPerson (app/domain/orders/sales_people.py) actually made this sale —
    # distinct from whichever User is logged in, since several people may share one login.
    sales_person_id: int
    items: list[QuotationItemIn]


class OutboxJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: OutboxStatus
    attempts: int
    # The full enqueue-time payload (customer_name, sales_person_name, created_by_username,
    # material_center_code, etc.) — exposed as-is rather than picking specific fields out,
    # so the admin dashboard and console can show whichever of these matter without a new
    # schema field every time one more gets added.
    payload: dict[str, Any] | None
    result: dict[str, Any] | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

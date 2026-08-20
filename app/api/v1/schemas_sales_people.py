"""Pydantic models for the sales-people (BUSY Executive master) endpoint."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SalesPersonOut(BaseModel):
    """A BUSY Executive (MasterType=33) — read-only, synced from BUSY like Product/
    MaterialCenter. Named "SalesPerson" on the wire since that's the concept our own app
    exposes; the underlying master is `Salesman` (app/db/models.py)."""

    model_config = ConfigDict(from_attributes=True)

    busy_code: int
    name: str
    alias: str | None
    is_active: bool
    updated_at: datetime

"""Pydantic response models for the catalog API — kept separate from the ORM models
(app/db/models.py) so the wire shape can evolve independently of storage."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    busy_code: int
    name: str
    price: Decimal
    unit: str
    item_group: str
    tracks_stock: bool
    is_active: bool
    woo_product_id: int | None
    barcode: str | None
    updated_at: datetime


class ProductBarcodeUpdateRequest(BaseModel):
    barcode: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    busy_group_name: str
    woo_category_id: int | None


class MaterialCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    busy_code: int
    name: str
    alias: str | None
    parent_group: str | None
    is_active: bool
    updated_at: datetime


class SyncRequest(BaseModel):
    full: bool = False


class SyncTriggerResponse(BaseModel):
    status: str


class SyncStatusEntryOut(BaseModel):
    entity: str
    last_stamp: int
    updated_at: datetime


class WooSyncStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seeded: bool
    last_run_at: datetime | None
    last_seeded: int
    last_created: int
    last_updated: int
    last_skipped: int
    last_failed: int


class SyncStatusResponse(BaseModel):
    busy: list[SyncStatusEntryOut]
    woocommerce: WooSyncStatusOut

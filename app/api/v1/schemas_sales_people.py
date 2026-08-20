"""Pydantic models for the sales-people endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SalesPersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    material_center_code: int
    is_active: bool
    created_at: datetime


class SalesPersonCreateRequest(BaseModel):
    full_name: str
    material_center_code: int


class SalesPersonReassignRequest(BaseModel):
    material_center_code: int | None = None
    is_active: bool | None = None

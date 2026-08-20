"""Pydantic models for the auth endpoints — separate from schemas.py (catalog), same
pattern as schemas_outbox.py."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str
    material_center_code: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    material_center_code: int
    is_active: bool
    is_superadmin: bool
    created_at: datetime


class CurrentUserOut(BaseModel):
    id: int
    username: str
    full_name: str
    material_center_code: int
    material_center_name: str
    is_superadmin: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

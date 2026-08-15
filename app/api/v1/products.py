"""Product routes — thin: parse/validate input, call the domain layer, return its result
(CLAUDE.md §3). Never touches BUSY; only ever reads MySQL (Sprint 1 DoD)."""

from fastapi import APIRouter, HTTPException

from app.api.v1.deps import DbSession
from app.api.v1.schemas import ProductOut
from app.domain.catalog.queries import get_product, list_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products_route(
    db: DbSession,
    search: str | None = None,
    category: str | None = None,
    active: bool | None = None,
) -> list[ProductOut]:
    products = list_products(db, search=search, category=category, active=active)
    return [ProductOut.model_validate(p) for p in products]


@router.get("/{code}", response_model=ProductOut)
def get_product_route(code: int, db: DbSession) -> ProductOut:
    product = get_product(db, code)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)

"""Product routes — thin: parse/validate input, call the domain layer, return its result
(CLAUDE.md §3). Never touches BUSY; only ever reads MySQL (Sprint 1 DoD)."""

from fastapi import APIRouter, HTTPException, status

from app.api.v1.deps import DbSession, SuperadminUser
from app.api.v1.schemas import ProductBarcodeUpdateRequest, ProductOut
from app.domain.catalog.queries import (
    DuplicateBarcodeError,
    ProductNotFoundError,
    get_product,
    list_products,
    set_product_barcode,
)

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


@router.put("/{code}/barcode", response_model=ProductOut)
def set_product_barcode_route(
    code: int, body: ProductBarcodeUpdateRequest, db: DbSession, _: SuperadminUser
) -> ProductOut:
    """Assign a barcode to a product — superadmin-only. Local-only field (CLAUDE.md §8:
    this company's real Item master has no barcode data), survives catalog re-syncs."""
    try:
        product = set_product_barcode(db, code, body.barcode)
    except ProductNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found") from exc
    except DuplicateBarcodeError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "barcode already assigned to a different product"
        ) from exc
    return ProductOut.model_validate(product)

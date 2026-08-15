"""Category routes — thin (CLAUDE.md §3)."""

from fastapi import APIRouter

from app.api.v1.deps import DbSession
from app.api.v1.schemas import CategoryOut
from app.domain.catalog.queries import list_categories

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories_route(db: DbSession) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in list_categories(db)]

"""Material Center (branch) routes — thin (CLAUDE.md §3)."""

from fastapi import APIRouter

from app.api.v1.deps import DbSession
from app.api.v1.schemas import MaterialCenterOut
from app.domain.catalog.queries import list_material_centers

router = APIRouter(prefix="/material-centers", tags=["material-centers"])


@router.get("", response_model=list[MaterialCenterOut])
def list_material_centers_route(db: DbSession) -> list[MaterialCenterOut]:
    return [MaterialCenterOut.model_validate(mc) for mc in list_material_centers(db)]

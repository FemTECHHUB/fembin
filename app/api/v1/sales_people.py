"""Sales-people routes — thin (CLAUDE.md §3). Read-only: this is BUSY's own Executive
master (MasterType=33), synced like Product/MaterialCenter, not something we create or
edit from our side (app/db/models.py's `Salesman` docstring has the full story)."""

from fastapi import APIRouter

from app.api.v1.deps import DbSession
from app.api.v1.schemas_sales_people import SalesPersonOut
from app.domain.catalog.queries import list_salesmen

router = APIRouter(prefix="/sales-people", tags=["sales-people"])


@router.get("", response_model=list[SalesPersonOut])
def list_sales_people_route(db: DbSession) -> list[SalesPersonOut]:
    return [SalesPersonOut.model_validate(p) for p in list_salesmen(db)]

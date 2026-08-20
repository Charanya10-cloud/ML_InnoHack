from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchResponse
from app.services.search_service import run_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, description="Free-text query over title/abstract"),
    disease_area: str | None = Query(None, description="Filter to one of the focus disease areas"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return run_search(db, query=q, disease_area=disease_area, limit=limit)

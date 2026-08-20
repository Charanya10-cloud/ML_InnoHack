from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    SignalDetailResponse,
    SignalIngestRequest,
    SignalIngestResponse,
    SignalListResponse,
)
from app.services.signal_service import (
    get_signal,
    ingest_signals,
    list_signals,
    to_signal_item,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=SignalListResponse)
def get_signals(
    disease_area: str | None = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return list_signals(db, disease_area=disease_area, min_score=min_score, limit=limit)


@router.get("/{signal_id}", response_model=SignalDetailResponse)
def get_signal_detail(signal_id: str, db: Session = Depends(get_db)):
    signal = get_signal(db, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return to_signal_item(signal)


@router.post("/ingest", response_model=SignalIngestResponse)
def post_signals_ingest(payload: SignalIngestRequest, db: Session = Depends(get_db)):
    """Called by ML's pipeline (Day 4) to hand off the finished, scored batch."""
    count = ingest_signals(db, payload)
    return SignalIngestResponse(inserted=count)

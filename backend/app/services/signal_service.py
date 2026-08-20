from sqlalchemy.orm import Session

from app.models import Signal
from app.schemas import (
    EvidenceItem,
    SignalIngestRequest,
    SignalItem,
    SignalListResponse,
)
from app.services.cache import signals_cache


def to_signal_item(s: Signal) -> SignalItem:
    return SignalItem(
        id=s.id,
        drug_name=s.drug_name,
        disease_name=s.disease_name,
        mechanism=s.mechanism,
        narrative=s.narrative,
        score=s.score,
        status=s.status,
        evidence=[EvidenceItem(**e) for e in (s.evidence or [])],
        created_at=s.created_at,
    )


def list_signals(db: Session, disease_area: str | None, min_score: float, limit: int) -> SignalListResponse:
    cache_key = f"{disease_area or ''}|{min_score}|{limit}"
    cached = signals_cache.get(cache_key)
    if cached is not None:
        return cached

    q = db.query(Signal).filter(Signal.score >= min_score)
    if disease_area:
        q = q.filter(Signal.disease_name.ilike(f"%{disease_area}%"))
    rows = q.order_by(Signal.score.desc()).limit(limit).all()

    response = SignalListResponse(
        total_results=len(rows),
        results=[to_signal_item(r) for r in rows],
    )
    signals_cache.set(cache_key, response)
    return response


def get_signal(db: Session, signal_id: str) -> Signal | None:
    return db.query(Signal).filter(Signal.id == signal_id).first()


def ingest_signals(db: Session, payload: SignalIngestRequest) -> int:
    """Replaces the current signal set with ML's freshly scored output.
    Simplest correct approach for a hackathon timeline: ML always sends the
    full, ranked batch; we clear stale signals rather than trying to diff."""
    db.query(Signal).delete()
    count = 0
    for item in payload.signals:
        db.add(
            Signal(
                drug_name=item.drug_name,
                disease_name=item.disease_name,
                mechanism=item.mechanism,
                narrative=item.narrative,
                score=item.score,
                status=item.status,
                evidence=[e.model_dump() for e in item.evidence],
            )
        )
        count += 1
    db.commit()
    signals_cache.clear()
    return count

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import RawDoc
from app.schemas import SearchResponse, SearchResultItem
from app.services.cache import search_cache


def run_search(db: Session, query: str, disease_area: str | None, limit: int) -> SearchResponse:
    cache_key = f"{query.lower().strip()}|{disease_area or ''}|{limit}"
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached

    like = f"%{query}%"
    q = db.query(RawDoc).filter(
        or_(RawDoc.title.ilike(like), RawDoc.abstract.ilike(like))
    )
    if disease_area:
        q = q.filter(RawDoc.disease_area.ilike(f"%{disease_area}%"))

    docs = q.order_by(RawDoc.published_at.desc().nullslast()).limit(limit).all()

    results = [
        SearchResultItem(
            doc_id=d.id,
            source=d.source,
            title=d.title,
            abstract_snippet=(d.abstract or "")[:280],
            url=d.url,
            disease_area=d.disease_area,
            published_at=d.published_at,
            # Placeholder relevance score until semantic ranking is wired in;
            # keeps the response shape stable for Frontend either way.
            relevance_score=1.0,
        )
        for d in docs
    ]

    response = SearchResponse(query=query, total_results=len(results), results=results)
    search_cache.set(cache_key, response)
    return response


def run_semantic_search(db: Session, embedding: list[float], disease_area: str | None, limit: int) -> SearchResponse:
    """Nearest-neighbor search over RawDoc.embedding using pgvector cosine distance.
    Only usable once docs have embeddings populated (see ingestion/embed step)."""
    q = db.query(RawDoc).filter(RawDoc.embedding.isnot(None))
    if disease_area:
        q = q.filter(RawDoc.disease_area.ilike(f"%{disease_area}%"))

    q = q.order_by(RawDoc.embedding.cosine_distance(embedding)).limit(limit)
    docs = q.all()

    results = [
        SearchResultItem(
            doc_id=d.id,
            source=d.source,
            title=d.title,
            abstract_snippet=(d.abstract or "")[:280],
            url=d.url,
            disease_area=d.disease_area,
            published_at=d.published_at,
            relevance_score=1.0,  # TODO: surface actual cosine distance once Frontend wants it
        )
        for d in docs
    ]
    return SearchResponse(query="[semantic]", total_results=len(results), results=results)

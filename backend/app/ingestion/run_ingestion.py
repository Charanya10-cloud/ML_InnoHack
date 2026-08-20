"""Run with: python -m app.ingestion.run_ingestion

Pulls documents from bioRxiv, PubMed, and ClinicalTrials.gov for each
disease area in DISEASE_FOCUS_AREAS, and upserts them into raw_docs.
This is what "real data flowing into Postgres" (Day 2) means in practice —
run this, then ML's extraction pipeline has rows to read.
"""

import sys
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.database import SessionLocal
from app.ingestion.biorxiv import fetch_biorxiv_docs
from app.ingestion.clinicaltrials import fetch_clinicaltrials_docs
from app.ingestion.pubmed import fetch_pubmed_docs
from app.models import RawDoc

FETCHERS = {
    "biorxiv": fetch_biorxiv_docs,
    "pubmed": fetch_pubmed_docs,
    "clinicaltrials": fetch_clinicaltrials_docs,
}


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def upsert_docs(db, docs: list[dict]) -> int:
    if not docs:
        return 0

    count = 0
    for doc in docs:
        stmt = pg_insert(RawDoc).values(
            source=doc["source"],
            source_id=doc["source_id"],
            title=doc["title"],
            abstract=doc.get("abstract", ""),
            url=doc.get("url", ""),
            published_at=_parse_date(doc.get("published_at")),
            disease_area=doc.get("disease_area", ""),
            raw_metadata=doc.get("raw_metadata", {}),
        )
        # On conflict (same source + source_id already ingested), just skip —
        # re-running ingestion should be idempotent, not create duplicates.
        stmt = stmt.on_conflict_do_nothing(constraint="uq_raw_docs_source_source_id")
        db.execute(stmt)
        count += 1

    db.commit()
    return count


def run(disease_areas: list[str] | None = None, max_docs_per_source: int = 50):
    settings = get_settings()
    areas = disease_areas or settings.focus_areas_list

    db = SessionLocal()
    total = 0
    try:
        for area in areas:
            print(f"[ingest] {area}")
            for source_name, fetcher in FETCHERS.items():
                try:
                    docs = fetcher(area, max_docs=max_docs_per_source)
                except Exception as exc:  # noqa: BLE001 - keep ingestion going across sources
                    print(f"  [{source_name}] FAILED: {exc}", file=sys.stderr)
                    continue
                n = upsert_docs(db, docs)
                total += n
                print(f"  [{source_name}] upserted {n} docs")
    finally:
        db.close()

    print(f"[ingest] done. {total} docs processed.")


if __name__ == "__main__":
    run()

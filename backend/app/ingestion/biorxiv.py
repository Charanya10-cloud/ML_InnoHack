"""Fetch recent bioRxiv preprints for a disease-area search term.

bioRxiv's public API is date-range based, not keyword-search based, so we
pull a recent window and filter client-side on title/abstract match. Good
enough for a hackathon-scale ingestion; swap for their Elasticsearch-backed
search if you need real keyword relevance later.
"""

from datetime import datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://api.biorxiv.org/details/biorxiv"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_page(start_date: str, end_date: str, cursor: int) -> dict:
    url = f"{BASE_URL}/{start_date}/{end_date}/{cursor}"
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_biorxiv_docs(disease_area: str, days_back: int = 180, max_docs: int = 100) -> list[dict]:
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)

    term_lower = disease_area.lower()
    docs: list[dict] = []
    cursor = 0

    while len(docs) < max_docs:
        page = _fetch_page(start_date.isoformat(), end_date.isoformat(), cursor)
        collection = page.get("collection", [])
        if not collection:
            break

        for item in collection:
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            if term_lower not in title.lower() and term_lower not in abstract.lower():
                continue
            docs.append(
                {
                    "source": "biorxiv",
                    "source_id": item.get("doi", ""),
                    "title": title,
                    "abstract": abstract,
                    "url": f"https://doi.org/{item.get('doi', '')}",
                    "published_at": item.get("date"),
                    "disease_area": disease_area,
                    "raw_metadata": item,
                }
            )
            if len(docs) >= max_docs:
                break

        cursor += len(collection)
        if len(collection) < 100:  # last page (API returns up to 100/page)
            break

    return docs

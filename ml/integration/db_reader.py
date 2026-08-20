# db_reader.py
#
# Job: read real ingested documents from Backend's Postgres "raw_docs"
# table, and reshape each row into the exact document format your
# pipeline already expects (the same shape tests/sample_abstracts.json
# used) -- so batch_extract.py doesn't need to change at all, it just
# gets its input from a different place.

from sqlalchemy import create_engine, text
from config import DATABASE_URL


def fetch_documents_from_db(disease_area: str = None, limit: int = 500) -> list:
    """
    Reads rows from Backend's raw_docs table and returns them as a list
    of dicts shaped like: {doc_id, source, title, abstract, published_date, url}

    disease_area: optional filter (e.g. "Alzheimer's disease") -- matches
    Backend's own disease_area column, set during their ingestion.
    limit: safety cap so a huge table doesn't accidentally get pulled
    all at once during testing.
    """

    engine = create_engine(DATABASE_URL)

    query = """
        SELECT id, source, title, abstract, url, published_at
        FROM raw_docs
        WHERE abstract IS NOT NULL AND abstract != ''
    """
    params = {}

    if disease_area:
        query += " AND disease_area ILIKE :disease_area"
        params["disease_area"] = f"%{disease_area}%"

    query += " ORDER BY published_at DESC NULLS LAST LIMIT :limit"
    params["limit"] = limit

    documents = []

    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        for row in result:
            # row.published_at is a Python datetime (or None) coming
            # straight from Postgres -- convert to a plain "YYYY-MM-DD"
            # string, matching what the rest of your pipeline expects.
            published_date = ""
            if row.published_at:
                published_date = row.published_at.strftime("%Y-%m-%d")

            documents.append({
                "doc_id": str(row.id),
                "source": row.source,
                "title": row.title or "",
                "abstract": row.abstract,
                "published_date": published_date,
                "url": row.url or ""
            })

    return documents


if __name__ == "__main__":
    # Quick manual test -- pulls a small batch and prints how many
    # documents came back, plus the first one, so you can eyeball that
    # the connection and shape are both correct before running it
    # through the full pipeline.
    docs = fetch_documents_from_db(limit=5)
    print(f"Fetched {len(docs)} documents.")
    if docs:
        import json
        print(json.dumps(docs[0], indent=2, default=str))
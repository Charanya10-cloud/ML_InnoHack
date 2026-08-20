# Drug Repurposing Signal API — Backend

FastAPI + Postgres (pgvector) backend for the drug-repurposing signal detection project.
Ingests bioRxiv / PubMed / ClinicalTrials.gov, and serves search + scored signals to the frontend.

## Quick start

```bash
cp .env.example .env          # edit NCBI_EMAIL, DISEASE_FOCUS_AREAS as needed
docker compose up --build     # starts Postgres (pgvector) + the API on :8000
```

API docs (Swagger UI): http://localhost:8000/docs

### Load data

```bash
# Real ingestion (hits bioRxiv/PubMed/ClinicalTrials.gov — run inside the api container
# or with DATABASE_URL pointed at localhost:5432 if running outside Docker):
docker compose exec api python -m app.ingestion.run_ingestion

# Mock signals so you can build against /signals before ML's pipeline is ready,
# and as a safe fallback for demo day:
docker compose exec api python -m app.ingestion.seed_demo_signals
```

### Local dev without Docker

```bash
pip install -r requirements.txt
# needs a running Postgres with the `vector` extension enabled (see db/init.sql)
uvicorn app.main:app --reload
```

## Architecture

```
app/
  main.py              FastAPI app, CORS, startup table creation
  config.py            env-driven settings (pydantic-settings)
  database.py          SQLAlchemy engine/session
  models.py            RawDoc, Entity, Relation, Signal tables (pgvector column on RawDoc)
  schemas.py            <- THE API CONTRACT, see below
  routers/
    search.py          GET /search
    signals.py          GET /signals, GET /signals/{id}, POST /signals/ingest
  services/
    search_service.py  keyword search now; cosine-similarity search once embeddings exist
    signal_service.py  serves + ingests ML's scored signals
    cache.py            in-memory TTL cache — pre-warm demo queries so nothing depends
                         on live DB/network during the pitch
  ingestion/
    biorxiv.py, pubmed.py, clinicaltrials.py   one fetcher per source
    run_ingestion.py    CLI: pulls all 3 sources for each DISEASE_FOCUS_AREAS entry,
                         upserts into raw_docs (idempotent — safe to re-run)
    seed_demo_signals.py  mock signals for early Frontend dev / demo fallback
```

## API contract (lock this with Frontend on Day 1)

### `GET /search?q=...&disease_area=...&limit=20`

```json
{
  "query": "metformin",
  "total_results": 2,
  "results": [
    {
      "doc_id": "uuid",
      "source": "pubmed",
      "title": "...",
      "abstract_snippet": "first 280 chars...",
      "url": "https://pubmed.ncbi.nlm.nih.gov/...",
      "disease_area": "Alzheimer's disease",
      "published_at": "2024-03-01T00:00:00",
      "relevance_score": 1.0
    }
  ]
}
```

### `GET /signals?disease_area=...&min_score=0.5&limit=20`

```json
{
  "total_results": 1,
  "results": [
    {
      "id": "uuid",
      "drug_name": "Metformin",
      "disease_name": "Non-small cell lung cancer",
      "mechanism": "AMPK activation suppressing mTOR-driven proliferation",
      "narrative": "Why this candidate makes sense, in plain English...",
      "score": 0.86,
      "status": "vetted",
      "evidence": [
        {"doc_id": "uuid", "title": "...", "url": "...", "snippet": "..."}
      ],
      "created_at": "2025-01-01T00:00:00"
    }
  ]
}
```

`GET /signals/{id}` returns a single signal object (same shape as one item above).

### `POST /signals/ingest` — ML's Day-4 handoff into the API

Request body:
```json
{
  "signals": [
    {
      "drug_name": "Metformin",
      "disease_name": "Non-small cell lung cancer",
      "mechanism": "...",
      "narrative": "...",
      "score": 0.86,
      "status": "vetted",
      "evidence": [{"doc_id": "...", "title": "...", "url": "...", "snippet": "..."}]
    }
  ]
}
```
Response: `{"inserted": 1}`

Calling this **replaces** the full signal set (simplest correct approach on a 5-day
timeline — ML always POSTs the complete, ranked batch rather than a diff).

### `GET /health` → `{"status": "ok", "env": "development"}`

## Demo-day reliability

`search_cache` and `signals_cache` (1hr TTL, in-memory) mean repeated identical
queries during the live demo hit memory, not the DB — run your 2-3 planned demo
queries once beforehand to warm the cache. `seed_demo_signals.py` also gives you
a guaranteed-good fallback dataset if live ingestion has issues on stage.

## Known simplifications (fine for a hackathon, flag if this becomes a real product)

- `run_ingestion.py` filters bioRxiv client-side (their public API isn't keyword-searchable).
- Semantic search (`run_semantic_search`) is wired up but needs an embedding column
  populated — add an embedding step to ingestion once ML picks a model (384-dim assumed,
  matching all-MiniLM-L6-v2; change `EMBEDDING_DIM` in `models.py` if you use something else).
- `POST /signals/ingest` has no auth — fine on a private demo network, not for prod.
- TTLCache is per-process/in-memory — fine for one Uvicorn worker; move to Redis if you
  ever run multiple workers.

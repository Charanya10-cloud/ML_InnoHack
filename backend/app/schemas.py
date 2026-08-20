from datetime import datetime

from pydantic import BaseModel, Field


# ---------- /search ----------

class SearchResultItem(BaseModel):
    doc_id: str
    source: str  # biorxiv | pubmed | clinicaltrials
    title: str
    abstract_snippet: str
    url: str
    disease_area: str
    published_at: datetime | None
    relevance_score: float


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[SearchResultItem]


# ---------- /signals ----------

class EvidenceItem(BaseModel):
    doc_id: str
    title: str
    url: str
    snippet: str = ""


class SignalItem(BaseModel):
    id: str
    drug_name: str
    disease_name: str
    mechanism: str
    narrative: str
    score: float
    status: str
    evidence: list[EvidenceItem]
    created_at: datetime


class SignalListResponse(BaseModel):
    total_results: int
    results: list[SignalItem]


class SignalDetailResponse(SignalItem):
    pass


# ---------- POST /signals/ingest (ML -> Backend handoff) ----------

class SignalIngestItem(BaseModel):
    drug_name: str
    disease_name: str
    mechanism: str = ""
    narrative: str = ""
    score: float = Field(ge=0, le=1)
    evidence: list[EvidenceItem] = []
    status: str = "candidate"


class SignalIngestRequest(BaseModel):
    signals: list[SignalIngestItem]


class SignalIngestResponse(BaseModel):
    inserted: int


# ---------- health ----------

class HealthResponse(BaseModel):
    status: str
    env: str

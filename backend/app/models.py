import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Embedding dimension for semantic search. 384 matches common small
# sentence-transformer models (e.g. all-MiniLM-L6-v2); change if ML swaps models.
EMBEDDING_DIM = 384


def gen_uuid():
    return str(uuid.uuid4())


class RawDoc(Base):
    """A single ingested document from bioRxiv, PubMed, or ClinicalTrials.gov."""

    __tablename__ = "raw_docs"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_raw_docs_source_source_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    source: Mapped[str] = mapped_column(String(32), index=True)  # biorxiv | pubmed | clinicaltrials
    source_id: Mapped[str] = mapped_column(String(128), index=True)  # DOI, PMID, NCT number
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(512), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disease_area: Mapped[str] = mapped_column(String(256), default="", index=True)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entities: Mapped[list["Entity"]] = relationship(back_populates="source_doc")


class Entity(Base):
    """A normalized drug, disease, or mechanism/pathway entity extracted by ML."""

    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_type_norm_id", "entity_type", "normalized_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(512), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # drug | disease | mechanism
    normalized_id: Mapped[str] = mapped_column(String(64), default="")  # RxNorm / MeSH ID
    normalized_source: Mapped[str] = mapped_column(String(32), default="")  # rxnorm | mesh
    source_doc_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("raw_docs.id"), nullable=True
    )

    source_doc: Mapped["RawDoc | None"] = relationship(back_populates="entities")


class Relation(Base):
    """A drug-disease-mechanism relation extracted from a document."""

    __tablename__ = "relations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    subject_entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"))
    object_entity_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("entities.id"))
    relation_type: Mapped[str] = mapped_column(String(64))  # targets | treats | implicated_in ...
    evidence_doc_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("raw_docs.id"))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    subject_entity: Mapped["Entity"] = relationship(foreign_keys=[subject_entity_id])
    object_entity: Mapped["Entity"] = relationship(foreign_keys=[object_entity_id])
    evidence_doc: Mapped["RawDoc"] = relationship(foreign_keys=[evidence_doc_id])


class Signal(Base):
    """A scored drug-repurposing candidate produced by ML's graph/signal pipeline.

    ML posts finished, pre-scored signals here via POST /signals/ingest; the API
    then just serves them (fast, cacheable) rather than recomputing anything live.
    """

    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    drug_name: Mapped[str] = mapped_column(String(512), index=True)
    disease_name: Mapped[str] = mapped_column(String(512), index=True)
    mechanism: Mapped[str] = mapped_column(Text, default="")
    narrative: Mapped[str] = mapped_column(Text, default="")  # human-readable "why this works"
    score: Mapped[float] = mapped_column(Float, index=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # list of {doc_id, title, url, snippet}
    status: Mapped[str] = mapped_column(String(16), default="candidate")  # candidate | vetted | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

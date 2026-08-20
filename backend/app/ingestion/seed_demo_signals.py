"""Run with: python -m app.ingestion.seed_demo_signals

Loads a handful of realistic mock signals so Frontend can build against
/signals before ML's pipeline produces real output, and so the demo has a
guaranteed-safe fallback query if live data has issues on stage.
Safe to re-run: it clears and replaces the signals table each time.
"""

from app.database import SessionLocal
from app.schemas import EvidenceItem, SignalIngestItem, SignalIngestRequest
from app.services.signal_service import ingest_signals

DEMO_SIGNALS = [
    SignalIngestItem(
        drug_name="Metformin",
        disease_name="Non-small cell lung cancer",
        mechanism="AMPK activation suppressing mTOR-driven tumor cell proliferation",
        narrative=(
            "Metformin activates AMPK, which inhibits mTOR signaling implicated in "
            "NSCLC proliferation. Multiple observational studies link metformin use "
            "in diabetic patients to lower NSCLC incidence and improved response to "
            "standard chemotherapy."
        ),
        score=0.86,
        status="vetted",
        evidence=[
            EvidenceItem(
                doc_id="demo-doc-1",
                title="AMPK activation and mTOR suppression in NSCLC models",
                url="https://pubmed.ncbi.nlm.nih.gov/",
                snippet="Metformin-treated NSCLC cell lines showed reduced mTOR pathway activity.",
            )
        ],
    ),
    SignalIngestItem(
        drug_name="Sildenafil",
        disease_name="Alzheimer's disease",
        mechanism="PDE5 inhibition increasing cGMP and cerebral blood flow",
        narrative=(
            "Sildenafil's PDE5 inhibition raises cGMP levels, which has been linked "
            "to improved synaptic plasticity and reduced amyloid pathology in animal "
            "models, with real-world claims-data analyses associating sildenafil use "
            "with lower Alzheimer's incidence."
        ),
        score=0.79,
        status="vetted",
        evidence=[
            EvidenceItem(
                doc_id="demo-doc-2",
                title="PDE5 inhibitors and amyloid-beta clearance",
                url="https://pubmed.ncbi.nlm.nih.gov/",
                snippet="cGMP elevation correlated with reduced amyloid plaque burden.",
            )
        ],
    ),
    SignalIngestItem(
        drug_name="Metformin",
        disease_name="Alzheimer's disease",
        mechanism="AMPK-mediated reduction of neuroinflammation",
        narrative=(
            "AMPK activation by metformin reduces neuroinflammatory markers "
            "implicated in Alzheimer's progression; several cohort studies show "
            "association but causal trial evidence is still limited."
        ),
        score=0.61,
        status="candidate",
        evidence=[],
    ),
]


def run():
    db = SessionLocal()
    try:
        count = ingest_signals(db, SignalIngestRequest(signals=DEMO_SIGNALS))
        print(f"[seed] inserted {count} demo signals")
    finally:
        db.close()


if __name__ == "__main__":
    run()

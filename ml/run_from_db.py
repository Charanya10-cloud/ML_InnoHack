# run_from_db.py
#
# The "real data" version of your pipeline -- pulls actual ingested
# documents from Backend's Postgres database instead of your local
# test JSON, then runs the exact same extraction -> normalize -> graph
# steps as run_pipeline.py.
#
# PREREQUISITES before running this:
#   1. Backend's API + Postgres must be running and reachable
#   2. Backend's ingestion must have ALREADY been run at least once
#      (python -m app.ingestion.run_ingestion from the backend/ folder)
#      -- otherwise raw_docs is empty and this will fetch 0 documents.

import pickle
import os

from integration.db_reader import fetch_documents_from_db
from batch_extract import run_batch_on_documents
from normalization.dedupe import normalize_extraction
from graph.build_graph import build_graph_from_documents, print_graph_summary
from config import OUTPUT_DIR


def normalize_all_documents(documents: list) -> list:
    """Same logic as run_pipeline.py -- normalizes every document's
    extracted entities/relations consistently."""
    normalized_documents = []
    for doc in documents:
        normalized_doc = {
            "doc_id": doc["doc_id"],
            "source": doc.get("source", ""),
            "title": doc.get("title", ""),
            "published_date": doc.get("published_date", ""),
            "url": doc.get("url", ""),
            "extraction": normalize_extraction(doc["extraction"])
        }
        normalized_documents.append(normalized_doc)
    return normalized_documents


def run(disease_area: str = None, limit: int = 200):
    print(f"Fetching documents from database (disease_area={disease_area!r}, limit={limit})...")
    docs = fetch_documents_from_db(disease_area=disease_area, limit=limit)
    print(f"Fetched {len(docs)} documents.")

    if not docs:
        print("No documents found. Has Backend's ingestion been run yet? "
              "(python -m app.ingestion.run_ingestion from the backend/ folder)")
        return

    print("Running extraction on real documents (this may take a while)...")
    extracted = run_batch_on_documents(docs, output_filename="extracted_entities_real.json")

    print("Normalizing entities and relations...")
    normalized = normalize_all_documents(extracted)

    normalized_path = os.path.join(OUTPUT_DIR, "normalized_entities_real.json")
    import json
    with open(normalized_path, "w") as f:
        json.dump(normalized, f, indent=2)
    print(f"Normalized data saved to {normalized_path}")

    print("Building knowledge graph...")
    graph = build_graph_from_documents(normalized)

    graph_path = os.path.join(OUTPUT_DIR, "knowledge_graph.pkl")
    with open(graph_path, "wb") as f:
        pickle.dump(graph, f)
    print(f"Graph saved to {graph_path}")

    print()
    print_graph_summary(graph)


if __name__ == "__main__":
    # Adjust disease_area to match whatever Backend's DISEASE_FOCUS_AREAS
    # setting used during ingestion (check backend/.env).
    run(disease_area="Alzheimer's disease", limit=200)
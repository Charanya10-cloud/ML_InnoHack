# run_pipeline.py
#
# This is the "glue" script that connects everything you've built so far
# into one real pipeline, running on your ACTUAL extracted data instead
# of hand-written test documents:
#
#   output/extracted_entities.json (raw, from batch_extract.py)
#       -> normalize each document's extraction
#       -> build one combined knowledge graph
#       -> save the graph to disk so signals/detector.py can use it later
#
# Run this AFTER batch_extract.py has already produced output/extracted_entities.json

import json
import os
import pickle

from normalization.dedupe import normalize_extraction
from graph.build_graph import build_graph_from_documents, print_graph_summary
from config import OUTPUT_DIR


def load_extracted_documents(filepath: str) -> list:
    with open(filepath, "r") as f:
        return json.load(f)


def normalize_all_documents(documents: list) -> list:
    """
    Takes the raw list of extracted documents and returns a new list
    where every document's "extraction" field has been run through
    normalize_extraction(). The doc_id/source/published_date stay
    the same -- only the extracted entities/relations inside get cleaned.
    """
    normalized_documents = []

    for doc in documents:
        normalized_doc = {
            "doc_id": doc["doc_id"],
            "source": doc.get("source", ""),
            "title": doc.get("title", ""),
            "published_date": doc.get("published_date", ""),
            "extraction": normalize_extraction(doc["extraction"])
        }
        normalized_documents.append(normalized_doc)

    return normalized_documents


def run_pipeline():
    extracted_path = os.path.join(OUTPUT_DIR, "extracted_entities.json")
    normalized_path = os.path.join(OUTPUT_DIR, "normalized_entities.json")
    graph_path = os.path.join(OUTPUT_DIR, "knowledge_graph.pkl")

    print(f"Loading extracted data from {extracted_path}...")
    documents = load_extracted_documents(extracted_path)
    print(f"Loaded {len(documents)} documents.")

    print("Normalizing entities and relations across all documents...")
    normalized_documents = normalize_all_documents(documents)

    # Save the normalized data too -- useful for manually inspecting
    # what changed, and for Research to sanity-check without needing
    # to run any code themselves.
    with open(normalized_path, "w") as f:
        json.dump(normalized_documents, f, indent=2)
    print(f"Normalized data saved to {normalized_path}")

    print("Building knowledge graph...")
    graph = build_graph_from_documents(normalized_documents)

    # Save the graph itself to disk using pickle -- this lets
    # signals/detector.py load the already-built graph directly,
    # instead of rebuilding it from scratch every time.
    with open(graph_path, "wb") as f:
        pickle.dump(graph, f)
    print(f"Graph saved to {graph_path}")

    print()
    print_graph_summary(graph)


if __name__ == "__main__":
    run_pipeline()
    
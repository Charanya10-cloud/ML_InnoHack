# batch_extract.py
#
# Job: take a LIST of abstracts (like the ones in tests/sample_abstracts.json,
# or later, real data from Backend) -> run extract_entities() on each one ->
# save all results to a single output file.
#
# This is basically a loop around the function we already built and tested.
# Nothing new conceptually -- just doing it many times and saving progress
# safely.

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extraction.extract_entities import extract_entities
from config import OUTPUT_DIR


def load_abstracts(filepath: str) -> list:
    """Reads a JSON file containing a list of abstract records."""
    with open(filepath, "r") as f:
        return json.load(f)


def run_batch_on_documents(documents: list, output_filename: str = "extracted_entities.json"):
    """
    Runs extraction on an ALREADY-LOADED list of documents (regardless of
    whether they came from a local JSON file or straight from the
    database) and saves results the same way as before.

    This is the shared core -- run_batch() below is just a thin wrapper
    around this for the "load from a file" case.
    """
    results = []

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print(f"Starting extraction on {len(documents)} documents...")

    for i, record in enumerate(documents):
        print(f"  [{i + 1}/{len(documents)}] Extracting doc_id={record['doc_id']}...")

        extraction = extract_entities(record["abstract"])

        combined = {
            "doc_id": record["doc_id"],
            "source": record.get("source", ""),
            "title": record.get("title", ""),
            "published_date": record.get("published_date", ""),
            "url": record.get("url", ""),
            "extraction": extraction
        }

        results.append(combined)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

    print(f"Done. Results saved to {output_path}")
    return results


def run_batch(input_filepath: str, output_filename: str = "extracted_entities.json"):
    """Loads documents from a local JSON file, then runs the shared
    extraction loop above. Use this for your test data."""
    documents = load_abstracts(input_filepath)
    return run_batch_on_documents(documents, output_filename)


if __name__ == "__main__":
    # Point this at your test file for now. Later, Backend will hand you
    # a real file of ingested abstracts in this same shape, and you'll
    # just swap the filepath here.
    run_batch(
        input_filepath="tests/sample_abstracts.json",
        output_filename="extracted_entities.json"
    )
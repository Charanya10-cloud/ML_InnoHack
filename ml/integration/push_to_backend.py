# push_to_backend.py
#
# Job: take your scored candidate signals (from detector.py + scorer.py)
# and do two things:
#   1. Convert them into the EXACT shape Backend's /signals/ingest
#      endpoint expects (SignalIngestRequest, from their schemas.py)
#   2. POST them there
#
# This is the actual handoff point between ML and Backend.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from config import BACKEND_API_URL

# Human-readable phrasing for each relation type -- used to turn your
# structured mechanism_path into a plain-English sentence, since
# Backend's schema wants a "mechanism" STRING, not a list of steps.
RELATION_PHRASES = {
    "ACTIVATES": "activates",
    "INHIBITS": "inhibits",
    "TARGETS": "targets",
    "MODULATES": "modulates",
    "IMPLICATED_IN": "is implicated in",
    "STUDIED_FOR": "is studied for",
}


def _build_mechanism_string(signal: dict) -> str:
    """
    Turns a mechanism_path like:
      [{"type": "MODULATES", "source": "Statins", "target": "NF-kB"},
       {"type": "IMPLICATED_IN", "source": "NF-kB", "target": "Rheumatoid Arthritis"}]
    into a plain sentence:
      "Statins modulates NF-kB, which is implicated in Rheumatoid Arthritis."
    """
    path = signal["mechanism_path"]
    if not path:
        return ""

    first_step = path[0]
    phrase = RELATION_PHRASES.get(first_step["type"], first_step["type"].lower())
    sentence = f"{first_step['source']} {phrase} {first_step['target']}"

    for step in path[1:]:
        phrase = RELATION_PHRASES.get(step["type"], step["type"].lower())
        sentence += f", which {phrase} {step['target']}"

    return sentence + "."


def _build_narrative(signal: dict, mechanism_str: str) -> str:
    """
    Builds the longer, human-readable "why this works" narrative Backend
    displays to users. Deliberately includes an honest caveat about what
    trial_gap_confirmed actually means -- see detector.py's note on this.
    """
    unique_doc_ids = {e["doc_id"] for e in signal["evidence"]}
    doc_count = len(unique_doc_ids)
    doc_word = "document" if doc_count == 1 else "documents"

    narrative = (
        f"{mechanism_str} This mechanism is supported by {doc_count} "
        f"{doc_word} in our ingested literature. "
    )
    narrative += (
        "Note: this signal reflects an absence of evidence in our own "
        "corpus, not a confirmed absence of clinical trials -- treat as "
        "a research lead, not a validated finding."
    )
    return narrative


def _build_evidence_items(signal: dict) -> list:
    """
    Converts your evidence list into Backend's EvidenceItem shape:
    {doc_id, title, url, snippet}. Deduplicates by doc_id first, since
    a 2-hop signal can have multiple evidence entries from the SAME
    document (one per hop) -- Backend just wants one entry per source.
    """
    seen_doc_ids = set()
    items = []

    for e in signal["evidence"]:
        if e["doc_id"] in seen_doc_ids:
            continue
        seen_doc_ids.add(e["doc_id"])

        items.append({
            "doc_id": e["doc_id"],
            "title": e.get("title", "") or "(untitled)",
            "url": e.get("url", ""),
            "snippet": e["evidence_sentence"]
        })

    return items


def package_signal(signal: dict) -> dict:
    """Converts ONE of your scored signals into Backend's SignalIngestItem shape."""
    mechanism_str = _build_mechanism_string(signal)

    return {
        "drug_name": signal["drug"]["name"],
        "disease_name": signal["disease"]["name"],
        "mechanism": mechanism_str,
        "narrative": _build_narrative(signal, mechanism_str),
        "score": signal["scores"]["overall"],
        "evidence": _build_evidence_items(signal),
        "status": "candidate"
    }


def package_all_signals(scored_signals: list) -> dict:
    """Wraps everything into the full SignalIngestRequest shape:
    { "signals": [ ... ] }"""
    return {
        "signals": [package_signal(s) for s in scored_signals]
    }


def push_signals(scored_signals: list, dry_run: bool = False):
    """
    Packages and POSTs the signals to Backend's /signals/ingest endpoint.

    dry_run=True: builds the payload and prints it, but does NOT actually
    send it -- useful for checking the shape looks right before you have
    Backend's server running locally.
    """
    payload = package_all_signals(scored_signals)

    if dry_run:
        import json
        print(json.dumps(payload, indent=2))
        print(f"\n(dry run -- {len(payload['signals'])} signal(s) NOT sent)")
        return

    url = f"{BACKEND_API_URL}/signals/ingest"
    response = httpx.post(url, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    print(f"Pushed {len(payload['signals'])} signal(s). "
          f"Backend confirmed {result.get('inserted', '?')} inserted.")


if __name__ == "__main__":
    from signals.detector import load_graph, find_candidate_signals
    from signals.scorer import score_all_candidates

    graph = load_graph("output/knowledge_graph.pkl")
    candidates = find_candidate_signals(graph)
    scored = score_all_candidates(candidates, graph)

    # Start with dry_run=True until Backend's server is confirmed running
    # locally -- flip to False once you're ready to actually send.
    push_signals(scored, dry_run=False)
# scorer.py
#
# Job: take the candidate signals from detector.py and score each one
# 0-1, so they can be RANKED -- turning "here are some candidates" into
# "here's which one deserves a researcher's attention first."
#
# Four sub-scores combine into one overall score. Each is deliberately
# simple and explainable -- you should be able to point at any score on
# stage and say exactly why it's that number, rather than "the model
# said so."

from datetime import datetime, date
import networkx as nx

# How strong/direct each relation type is, as a claim. ACTIVATES/INHIBITS
# are specific, mechanistic claims -- MODULATES is deliberately weaker
# since it comes from softer language ("effects on") rather than a
# precise mechanism.
RELATION_STRENGTH = {
    "ACTIVATES": 1.0,
    "INHIBITS": 1.0,
    "TARGETS": 0.9,
    "MODULATES": 0.6,
    "IMPLICATED_IN": 0.8,
    "STUDIED_FOR": 1.0,
}

# Evidence older than this many days scores close to 0 on recency --
# tune this based on how fast-moving your chosen disease areas are.
RECENCY_WINDOW_DAYS = 730  # ~2 years

# Weights for combining sub-scores into one overall score. Must sum to 1.0.
SCORE_WEIGHTS = {
    "evidence_strength": 0.35,
    "recency": 0.15,
    "safety_proxy": 0.25,
    "mechanistic_distance": 0.25,
}


def _score_evidence_strength(signal: dict) -> float:
    """More independent supporting documents = stronger evidence.
    We cap at 3 unique documents = a perfect score, since demanding
    more than that is unrealistic at hackathon data scale."""
    unique_doc_ids = {e["doc_id"] for e in signal["evidence"]}
    return min(1.0, len(unique_doc_ids) / 3)


def _score_recency(signal: dict) -> float:
    """More recent evidence scores higher. Uses the MOST RECENT
    publication date among all evidence for this signal."""
    dates = []
    for e in signal["evidence"]:
        try:
            dates.append(datetime.strptime(e["published_date"], "%Y-%m-%d").date())
        except (ValueError, KeyError):
            continue  # skip evidence with missing/malformed dates

    if not dates:
        return 0.5  # neutral score if we have no date info at all

    most_recent = max(dates)
    days_old = (date.today() - most_recent).days
    days_old = max(0, days_old)  # guard against future-dated test data

    recency_score = 1 - (days_old / RECENCY_WINDOW_DAYS)
    return max(0.0, min(1.0, recency_score))  # clip to [0, 1]


def _score_safety_proxy(signal: dict, G: nx.MultiDiGraph) -> float:
    """A drug that's already studied/approved for SOME disease is a
    lower-risk repurposing candidate than a totally novel compound.
    Checks if the drug has ANY 'STUDIED_FOR' edge in the graph at all,
    regardless of which disease it points to."""
    drug_name = signal["drug"]["name"]

    if drug_name not in G:
        return 0.3  # drug not even in the graph as a node -- shouldn't
                     # normally happen, but guard against it anyway

    for _, _, key in G.out_edges(drug_name, keys=True):
        if key == "STUDIED_FOR":
            return 1.0

    return 0.3  # no known established use found -- more novel, riskier


def _score_mechanistic_distance(signal: dict) -> float:
    """Averages the relation-strength of each hop in the mechanism path.
    A path made of two strong, direct relations scores higher than one
    with a soft MODULATES hop in it."""
    strengths = [
        RELATION_STRENGTH.get(step["type"], 0.5)  # 0.5 = unknown relation type fallback
        for step in signal["mechanism_path"]
    ]
    return sum(strengths) / len(strengths) if strengths else 0.5


def score_signal(signal: dict, G: nx.MultiDiGraph) -> dict:
    """
    Takes ONE candidate signal (from detector.py) and returns a NEW
    dict with a "scores" field added, matching the /signals API
    contract shape we agreed with Backend.
    """
    evidence_strength = _score_evidence_strength(signal)
    recency = _score_recency(signal)
    safety_proxy = _score_safety_proxy(signal, G)
    mechanistic_distance = _score_mechanistic_distance(signal)

    overall = (
        evidence_strength * SCORE_WEIGHTS["evidence_strength"] +
        recency * SCORE_WEIGHTS["recency"] +
        safety_proxy * SCORE_WEIGHTS["safety_proxy"] +
        mechanistic_distance * SCORE_WEIGHTS["mechanistic_distance"]
    )

    scored_signal = dict(signal)  # copy, don't mutate the original
    scored_signal["scores"] = {
        "overall": round(overall, 2),
        "evidence_strength": round(evidence_strength, 2),
        "recency": round(recency, 2),
        "safety_proxy": round(safety_proxy, 2),
        "mechanistic_distance": round(mechanistic_distance, 2),
    }
    return scored_signal


def score_all_candidates(candidates: list, G: nx.MultiDiGraph) -> list:
    """Scores every candidate and returns them sorted by overall score,
    highest (most promising) first."""
    scored = [score_signal(c, G) for c in candidates]
    scored.sort(key=lambda s: s["scores"]["overall"], reverse=True)
    return scored


def print_scored_candidates(scored_candidates: list):
    print(f"Ranked signals ({len(scored_candidates)} total):\n")

    for signal in scored_candidates:
        drug = signal["drug"]["name"]
        disease = signal["disease"]["name"]
        scores = signal["scores"]

        print(f"  {signal['signal_id']}: {drug} -> {disease}  "
              f"[overall: {scores['overall']}]")
        print(f"    evidence_strength={scores['evidence_strength']}  "
              f"recency={scores['recency']}  "
              f"safety_proxy={scores['safety_proxy']}  "
              f"mechanistic_distance={scores['mechanistic_distance']}")
        print()


if __name__ == "__main__":
    # detector.py lives in this same folder, so this import works
    # directly when you run this file from the ml/ project root.
    from detector import load_graph, find_candidate_signals

    graph = load_graph("output/knowledge_graph.pkl")
    candidates = find_candidate_signals(graph)
    scored = score_all_candidates(candidates, graph)
    print_scored_candidates(scored)
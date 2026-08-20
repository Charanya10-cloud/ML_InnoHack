# detector.py
#
# Job: walk the knowledge graph looking for Drug -> Target -> Disease
# paths where the drug has NO existing direct "STUDIED_FOR" connection
# to that disease. Each one found is a candidate repurposing signal.
#
# IMPORTANT HONESTY NOTE: "no STUDIED_FOR edge" means no evidence of
# this drug-disease pairing was found in OUR ingested literature. It is
# a proxy, not a real check against ClinicalTrials.gov. A real trial-gap
# check needs Backend's ClinicalTrials.gov data as a cross-reference --
# that's a clear integration point for later, not something to skip
# silently or oversell as already validated.

import pickle
import networkx as nx


def load_graph(path: str) -> nx.MultiDiGraph:
    with open(path, "rb") as f:
        return pickle.load(f)


def find_candidate_signals(G: nx.MultiDiGraph) -> list:
    """
    Walks the graph looking for Drug -> Target -> Disease paths.
    Returns a list of candidate signal dicts, shaped to match the
    /signals API contract we agreed with Backend (minus scores --
    that's scorer.py's job, next).
    """

    candidates = []
    signal_counter = 1

    drug_nodes = [n for n, data in G.nodes(data=True) if data.get("node_type") == "drug"]

    for drug in drug_nodes:
        # Step 1: find every TARGET this drug connects to, regardless
        # of relation type (ACTIVATES, INHIBITS, TARGETS all count --
        # what matters is that the drug affects this target somehow).
        for _, target, drug_target_key, drug_target_data in G.out_edges(drug, keys=True, data=True):
            if G.nodes[target].get("node_type") != "target":
                continue

            # Step 2: from that target, find every DISEASE it's
            # implicated in.
            for _, disease, target_disease_key, target_disease_data in G.out_edges(target, keys=True, data=True):
                if G.nodes[disease].get("node_type") != "disease":
                    continue
                if target_disease_data["relation_type"] != "IMPLICATED_IN":
                    continue

                # Step 3: the actual "gap" check -- does the drug
                # already have a direct STUDIED_FOR edge to this
                # disease? If so, this isn't a novel signal, skip it.
                already_studied = G.has_edge(drug, disease, key="STUDIED_FOR")
                if already_studied:
                    continue

                # Build the candidate signal, shaped to match what
                # Backend's /signals endpoint expects.
                signal = {
                    "signal_id": f"sig_{signal_counter:05d}",
                    "drug": {"name": drug},
                    "disease": {"name": disease},
                    "mechanism_path": [
                        {
                            "type": drug_target_data["relation_type"],
                            "source": drug,
                            "target": target
                        },
                        {
                            "type": target_disease_data["relation_type"],
                            "source": target,
                            "target": disease
                        }
                    ],
                    "trial_gap_confirmed": False,  # honest default -- see
                                                     # note below on why
                                                     # this isn't True yet
                    "evidence": drug_target_data["evidence"] + target_disease_data["evidence"]
                }

                candidates.append(signal)
                signal_counter += 1

    return candidates


def print_candidates(candidates: list):
    """Quick readable printout for sanity-checking candidates manually --
    this is exactly what Research should be looking at on Day 3."""

    print(f"Found {len(candidates)} candidate signal(s):\n")

    for signal in candidates:
        drug = signal["drug"]["name"]
        disease = signal["disease"]["name"]
        path_str = " -> ".join(
            [signal["mechanism_path"][0]["source"]] +
            [f"[{step['type']}] {step['target']}" for step in signal["mechanism_path"]]
        )

        # Count UNIQUE documents, not raw evidence entries -- a signal
        # spanning 2 hops always has at least 2 evidence entries (one
        # per hop) even if there's only 1 real supporting document, so
        # counting entries directly overstates how well-supported a
        # signal is.
        unique_doc_ids = {e["doc_id"] for e in signal["evidence"]}

        print(f"  {signal['signal_id']}: {drug} -> {disease}")
        print(f"    Path: {path_str}")
        print(f"    Evidence entries: {len(signal['evidence'])} "
              f"(from {len(unique_doc_ids)} unique document(s))")
        print()


if __name__ == "__main__":
    graph = load_graph("output/knowledge_graph.pkl")
    candidates = find_candidate_signals(graph)
    print_candidates(candidates)
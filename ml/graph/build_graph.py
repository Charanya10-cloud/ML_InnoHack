# build_graph.py
#
# Job: take normalized extraction results from MULTIPLE documents and
# combine them into ONE knowledge graph -- nodes are drugs/targets/
# diseases, edges are the relations between them (TARGETS, INHIBITS,
# IMPLICATED_IN, STUDIED_FOR).
#
# The key design decision here: if two different papers both support
# the SAME relation (e.g. "Metformin activates AMPK"), we don't create
# two edges -- we create ONE edge and attach both pieces of evidence to
# it. This is what lets your scoring step later count "how many
# independent papers support this" -- which is a big part of what makes
# a signal trustworthy versus a fluke.

import networkx as nx


def build_graph_from_documents(documents: list) -> nx.MultiDiGraph:
    """
    Takes a list of documents, where each document looks like:
    {
        "doc_id": "...",
        "source": "...",
        "published_date": "...",
        "extraction": { "drugs": [...], "diseases": [...],
                         "targets": [...], "relations": [...] }
    }
    (This is exactly the shape that batch_extract.py produces, after
    each document's "extraction" has been run through normalize_extraction().)

    Returns a networkx MultiDiGraph -- "Di" means directed (edges have
    a direction, e.g. Drug -> Target, not the reverse), "Multi" means
    more than one edge is allowed between the same two nodes (since a
    drug and target could have both a TARGETS relation and an INHIBITS
    relation between them, for example).
    """

    G = nx.MultiDiGraph()

    for doc in documents:
        extraction = doc["extraction"]
        doc_id = doc["doc_id"]
        source = doc.get("source", "")
        published_date = doc.get("published_date", "")

        # Add every entity as a node. node_type tells us later whether
        # we're looking at a drug, target, or disease when we query the
        # graph -- important since signal detection needs to walk
        # specifically Drug -> Target -> Disease paths.
        for drug in extraction.get("drugs", []):
            G.add_node(drug["name"], node_type="drug")

        for disease in extraction.get("diseases", []):
            G.add_node(disease["name"], node_type="disease")

        for target in extraction.get("targets", []):
            G.add_node(target["name"], node_type="target")

        # Add each relation as an edge, aggregating evidence if the
        # same relation already exists from an earlier document.
        for relation in extraction.get("relations", []):
            evidence_entry = {
                "doc_id": doc_id,
                "source": source,
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "published_date": published_date,
                "evidence_sentence": relation["evidence_sentence"]
            }

            _add_or_merge_edge(
                G,
                subject=relation["subject"],
                obj=relation["object"],
                relation_type=relation["relation_type"],
                evidence_entry=evidence_entry
            )

    return G


def _add_or_merge_edge(G, subject, obj, relation_type, evidence_entry):
    """
    Adds an edge from subject -> obj with the given relation_type.
    If this EXACT edge (same subject, same object, same relation_type)
    already exists -- meaning we've seen this claim before, from an
    earlier document -- we just append the new evidence to it instead
    of creating a duplicate edge.

    We use relation_type as the MultiDiGraph "key" -- this is what lets
    us have both a TARGETS edge AND an INHIBITS edge between the same
    two nodes without them overwriting each other.
    """
    if G.has_edge(subject, obj, key=relation_type):
        # Edge already exists -- just add this new evidence to it
        G[subject][obj][relation_type]["evidence"].append(evidence_entry)
    else:
        # First time seeing this exact relation -- create the edge
        G.add_edge(
            subject,
            obj,
            key=relation_type,
            relation_type=relation_type,
            evidence=[evidence_entry]
        )


def print_graph_summary(G: nx.MultiDiGraph):
    """Quick sanity-check printout -- how big is the graph, and what's
    in it. Useful every time you rebuild the graph from new data."""

    drug_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == "drug")
    target_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == "target")
    disease_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == "disease")

    print(f"Graph summary:")
    print(f"  Nodes: {G.number_of_nodes()} total "
          f"({drug_count} drugs, {target_count} targets, {disease_count} diseases)")
    print(f"  Edges: {G.number_of_edges()}")
    print()

    print("  Edges in the graph:")
    for subject, obj, key, data in G.edges(keys=True, data=True):
        evidence_count = len(data["evidence"])
        print(f"    {subject} --[{data['relation_type']}]--> {obj} "
              f"({evidence_count} supporting document(s))")


if __name__ == "__main__":
    # Manual test using two fake documents where the SAME relation
    # ("AMPK IMPLICATED_IN Polycystic Ovary Syndrome") is reported by
    # two different papers -- this is what proves the evidence-merging
    # logic actually works, rather than creating a duplicate edge.
    sample_documents = [
        {
            "doc_id": "test_001",
            "source": "PubMed",
            "published_date": "2025-11-02",
            "extraction": {
                "drugs": [{"name": "Metformin"}],
                "diseases": [{"name": "Type 2 Diabetes"}, {"name": "Polycystic Ovary Syndrome"}],
                "targets": [{"name": "AMPK"}],
                "relations": [
                    {"subject": "Metformin", "relation_type": "ACTIVATES",
                     "object": "AMPK", "evidence_sentence": "Metformin activates AMPK."},
                    {"subject": "AMPK", "relation_type": "IMPLICATED_IN",
                     "object": "Polycystic Ovary Syndrome",
                     "evidence_sentence": "AMPK is implicated in PCOS."}
                ]
            }
        },
        {
            "doc_id": "test_005",
            "source": "bioRxiv",
            "published_date": "2026-04-01",
            "extraction": {
                "drugs": [],
                "diseases": [{"name": "Polycystic Ovary Syndrome"}],
                "targets": [{"name": "AMPK"}],
                "relations": [
                    {"subject": "AMPK", "relation_type": "IMPLICATED_IN",
                     "object": "Polycystic Ovary Syndrome",
                     "evidence_sentence": "A second, independent paper also linking AMPK to PCOS."}
                ]
            }
        }
    ]

    graph = build_graph_from_documents(sample_documents)
    print_graph_summary(graph)
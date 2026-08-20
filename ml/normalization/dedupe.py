# dedupe.py
#
# Job: take ONE extraction result (the dict with drugs/diseases/targets/
# relations that extract_entities() produces) and normalize every name
# in it consistently -- so "PCOS" and "polycystic ovary syndrome" become
# the exact same string everywhere they appear, including inside relations.
#
# This runs AFTER extraction and BEFORE the graph gets built. Skipping
# this step is exactly what would cause your graph to end up with two
# disconnected nodes for what should be one disease.

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from normalization.drug_normalizer import normalize_drug_name
from normalization.disease_normalizer import normalize_disease_name


def _dedupe_name_list(names: list) -> list:
    """
    Takes a list of names that have ALREADY been normalized, and removes
    duplicates. Two normalized names might still differ only in casing
    from data noise, so we dedupe case-insensitively, keeping the first
    version we saw.
    """
    seen = {}
    for name in names:
        key = name.lower()
        if key not in seen:
            seen[key] = name
    return list(seen.values())


def normalize_extraction(extraction: dict) -> dict:
    """
    Takes one extraction result (matching the drugs/diseases/targets/
    relations shape) and returns a NEW dict with every name normalized
    and duplicates merged -- including inside the relations list, so
    everything stays consistent.

    Note: targets (genes/proteins like "AMPK", "mTOR") don't have a
    normalizer of their own yet -- gene names are already fairly
    standardized in scientific text, so we just clean up casing/
    whitespace for now. If you find real messy target names later,
    that's a sign to build a target_normalizer.py following the exact
    same pattern as the other two.
    """

    # Step 1: build a lookup table from RAW name -> NORMALIZED name,
    # for drugs and diseases. We need this same mapping again in a
    # moment when we fix up the relations list.
    drug_name_map = {}
    for drug in extraction.get("drugs", []):
        raw = drug["name"]
        drug_name_map[raw] = normalize_drug_name(raw)

    disease_name_map = {}
    for disease in extraction.get("diseases", []):
        raw = disease["name"]
        disease_name_map[raw] = normalize_disease_name(raw)

    # Targets: no dedicated normalizer yet, just clean whitespace/casing
    target_name_map = {}
    for target in extraction.get("targets", []):
        raw = target["name"]
        target_name_map[raw] = raw.strip()

    # Step 2: build the deduplicated top-level lists using the maps above
    normalized_drugs = _dedupe_name_list(list(drug_name_map.values()))
    normalized_diseases = _dedupe_name_list(list(disease_name_map.values()))
    normalized_targets = _dedupe_name_list(list(target_name_map.values()))

    # Step 3: fix up relations -- every subject/object needs to point to
    # the SAME normalized name we just used above, not the raw text.
    #
    # IMPORTANT: build this lookup keyed by LOWERCASE raw name, and look
    # up using .lower() too. Without this, a relation whose subject came
    # through with different casing than what ended up in the top-level
    # entity list (e.g. "statins" vs "Statins") would silently fail to
    # match, fall back to its raw uncorrected form, and end up as a
    # separate, wrongly-cased node in the graph -- disconnected from the
    # properly typed drug/disease/target nodes. This exact bug caused a
    # real signal to go missing without any error being raised.
    combined_map = {}
    for raw, norm in drug_name_map.items():
        combined_map[raw.lower()] = norm
    for raw, norm in disease_name_map.items():
        combined_map[raw.lower()] = norm
    for raw, norm in target_name_map.items():
        combined_map[raw.lower()] = norm

    normalized_relations = []
    seen_relations = set()  # avoid duplicate relations after normalization
    # merges two previously-different names into one

    for relation in extraction.get("relations", []):
        subject = combined_map.get(relation["subject"].lower(), relation["subject"])
        obj = combined_map.get(relation["object"].lower(), relation["object"])

        # Skip self-relations that might appear AFTER normalization merges
        # two previously-different names into the same one.
        if subject.lower() == obj.lower():
            continue

        # A relation is a duplicate if subject, relation_type, and object
        # all match one we've already kept -- doesn't matter if the
        # evidence sentence differs slightly in wording.
        dedupe_key = (subject.lower(), relation["relation_type"], obj.lower())
        if dedupe_key in seen_relations:
            continue
        seen_relations.add(dedupe_key)

        normalized_relations.append({
            "subject": subject,
            "relation_type": relation["relation_type"],
            "object": obj,
            "evidence_sentence": relation["evidence_sentence"]
        })

    return {
        "drugs": [{"name": d} for d in normalized_drugs],
        "diseases": [{"name": d} for d in normalized_diseases],
        "targets": [{"name": t} for t in normalized_targets],
        "relations": normalized_relations
    }


if __name__ == "__main__":
    # Quick manual test using a fake extraction result with the exact
    # PCOS/PCOS duplicate problem we saw in real output.
    sample_extraction = {
        "drugs": [{"name": "Metformin"}],
        "diseases": [
            {"name": "diabetes"},
            {"name": "polycystic ovary syndrome"},
            {"name": "PCOS"}
        ],
        "targets": [{"name": "AMPK"}],
        "relations": [
            {
                "subject": "Metformin",
                "relation_type": "ACTIVATES",
                "object": "AMPK",
                "evidence_sentence": "..."
            },
            {
                "subject": "AMPK",
                "relation_type": "IMPLICATED_IN",
                "object": "polycystic ovary syndrome",
                "evidence_sentence": "..."
            },
            {
                "subject": "AMPK",
                "relation_type": "IMPLICATED_IN",
                "object": "PCOS",
                "evidence_sentence": "..."
            }
        ]
    }

    import json
    result = normalize_extraction(sample_extraction)
    print(json.dumps(result, indent=2))
# extract_entities.py
#
# NO API CALLS -- everything runs locally.
#
# We now load TWO scispaCy models:
#   1. en_ner_bc5cdr_md      -> finds CHEMICAL (drug) and DISEASE entities
#   2. en_ner_bionlp13cg_md  -> finds GENE_OR_GENE_PRODUCT entities,
#                                which we treat as "targets"
#
# Why two models instead of one? Each scispaCy model is trained on a
# different labeled dataset, specialized for different entity types.
# There isn't one model that does all three well, so we run the same
# text through both and combine the results.

import sys
import os
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spacy
from config import (
    CHEM_DISEASE_MODEL_NAME,
    TARGET_MODEL_NAME,
    DRUG_TARGET_TRIGGERS,
    TARGET_DISEASE_TRIGGERS,
    DRUG_DISEASE_TRIGGERS,
    DRUG_BLOCKLIST,
)

print(f"Loading local model '{CHEM_DISEASE_MODEL_NAME}'...")
nlp_chem_disease = spacy.load(CHEM_DISEASE_MODEL_NAME)

print(f"Loading local model '{TARGET_MODEL_NAME}'...")
nlp_target = spacy.load(TARGET_MODEL_NAME)

print("Both models loaded.")


def _find_trigger(sentence_text: str, trigger_dict: dict) -> str | None:
    """Looks for any trigger word from trigger_dict in the sentence.
    Returns the matching relation type, or None if nothing matches."""
    lowered = sentence_text.lower()
    for trigger_word, relation_type in trigger_dict.items():
        if trigger_word in lowered:
            return relation_type
    return None


def _entities_in_range(entities, start_char, end_char):
    """Filters a list of (name, start_char, end_char) tuples down to
    only the ones that fall within a given character range -- this is
    how we figure out which entities belong to which sentence."""
    return [
        name for (name, e_start, e_end) in entities
        if e_start >= start_char and e_end <= end_char
    ]


def _mentions_in_sentence(sentence_text: str, known_names: list) -> list:
    """
    Given a list of names ALREADY confirmed as entities somewhere else
    in this document, check which ones are also textually mentioned in
    this specific sentence -- even if the model itself didn't tag them
    as an entity here.

    Why this is needed: NER models lean on capitalization as a strong
    cue. "Statins" at the start of a sentence gets recognized, but a
    later lowercase mention like "...suggests statins also reduce..."
    can be missed by the model in that specific spot, even though we
    already know "Statins" is a real drug from elsewhere in the same
    document. This is a simple, honest supplement -- not a replacement
    for the model, just a safety net for exactly this pattern.
    """
    lowered_sentence = sentence_text.lower()
    found = []
    for name in known_names:
        pattern = r"\b" + re.escape(name.lower()) + r"\b"
        if re.search(pattern, lowered_sentence):
            found.append(name)
    return found


def extract_entities(abstract_text: str) -> dict:
    """
    Takes a raw abstract as a string.
    Returns: { "drugs": [...], "diseases": [...], "targets": [...], "relations": [...] }

    Same output shape as before -- normalization/graph/signals code
    downstream doesn't need to change at all.
    """

    # Run the text through BOTH models. Each gives back its own `doc`
    # object, but since we passed in the exact same raw text to both,
    # character positions (start_char / end_char) line up between them --
    # that's what lets us combine their results correctly below.
    doc_cd = nlp_chem_disease(abstract_text)
    doc_target = nlp_target(abstract_text)

    # Collect all drug/disease entities as (name, start_char, end_char)
    all_drugs = []
    all_diseases = []
    for ent in doc_cd.ents:
        if ent.label_ == "CHEMICAL":
            name = ent.text.strip()
            # Skip known biomarkers/pathological substances that get
            # mislabeled as "drugs" -- see DRUG_BLOCKLIST for why.
            if name.lower() in DRUG_BLOCKLIST:
                continue
            all_drugs.append((name, ent.start_char, ent.end_char))
        elif ent.label_ == "DISEASE":
            all_diseases.append((ent.text.strip(), ent.start_char, ent.end_char))

    # Collect target (gene/protein) entities the same way
    all_targets = []
    for ent in doc_target.ents:
        if ent.label_ == "GENE_OR_GENE_PRODUCT":
            all_targets.append((ent.text.strip(), ent.start_char, ent.end_char))

    # Build the deduplicated top-level lists for our output
    drugs = _dedupe_entities(all_drugs)
    diseases = _dedupe_entities(all_diseases)
    targets = _dedupe_entities(all_targets)

    # Sanity fix: the target model sometimes mislabels a drug name as a
    # gene/protein (a false positive). If something is already confidently
    # a drug (from the specialized chemical/disease model), don't also
    # let it count as a target -- prevents nonsense like "Statins INHIBITS
    # Statins".
    drug_names_lower = {d.lower() for d in drugs}
    targets = [t for t in targets if t.lower() not in drug_names_lower]

    # Now go sentence by sentence (using doc_cd's sentence boundaries,
    # since sentence splitting only needs to happen once) and look for
    # relations WITHIN each sentence.
    relations = []

    for sent in doc_cd.sents:
        start, end = sent.start_char, sent.end_char
        sentence_text = sent.text.strip()

        # De-duplicate WITHIN this sentence -- a name mentioned twice in
        # one sentence (e.g. "mTOR signaling... mTOR activity...") should
        # only be paired once, not once per mention. Also drop any target
        # that got filtered out globally above (the drug/target overlap fix).
        target_names_lower = {t.lower() for t in targets}

        raw_drugs_here = _entities_in_range(all_drugs, start, end)
        raw_diseases_here = _entities_in_range(all_diseases, start, end)
        raw_targets_here = _entities_in_range(all_targets, start, end)

        # dict.fromkeys() is a simple trick to remove duplicates from a
        # list while keeping the original order -- a set alone would lose
        # ordering, and we don't need ordering to be perfect, but this is
        # a clean, readable way to do it either way.
        drugs_here = list(dict.fromkeys(raw_drugs_here))
        diseases_here = list(dict.fromkeys(raw_diseases_here))
        targets_here = [
            t for t in dict.fromkeys(raw_targets_here)
            if t.lower() in target_names_lower
        ]

        # Supplement with document-level known mentions the model might
        # have missed in THIS specific sentence (e.g. a lowercase repeat
        # mention). Only adds names we already confidently know about --
        # never invents a new entity that wasn't found anywhere.
        # Checked CASE-INSENSITIVELY, so a lowercase mention the model
        # already caught here (e.g. "statins") doesn't ALSO get the
        # properly-cased version ("Statins") added as a second, separate
        # entry -- that mismatch was the root cause of an earlier bug.
        drugs_here_lower = {d.lower() for d in drugs_here}
        for name in _mentions_in_sentence(sentence_text, drugs):
            if name.lower() not in drugs_here_lower:
                drugs_here.append(name)
                drugs_here_lower.add(name.lower())

        diseases_here_lower = {d.lower() for d in diseases_here}
        for name in _mentions_in_sentence(sentence_text, diseases):
            if name.lower() not in diseases_here_lower:
                diseases_here.append(name)
                diseases_here_lower.add(name.lower())

        targets_here_lower = {t.lower() for t in targets_here}
        for name in _mentions_in_sentence(sentence_text, targets):
            if name.lower() not in targets_here_lower:
                targets_here.append(name)
                targets_here_lower.add(name.lower())

        def _add_relation(subject, relation_type, obj):
            # Sanity guard: never let something be related to itself.
            if subject.lower() == obj.lower():
                return
            relations.append({
                "subject": subject,
                "relation_type": relation_type,
                "object": obj,
                "evidence_sentence": sentence_text
            })

        # Drug -> Target relations (e.g. "Metformin activates AMPK")
        if drugs_here and targets_here:
            relation_type = _find_trigger(sentence_text, DRUG_TARGET_TRIGGERS)
            if relation_type:
                for drug in drugs_here:
                    for target in targets_here:
                        _add_relation(drug, relation_type, target)

        # Target -> Disease relations (e.g. "AMPK is implicated in PCOS")
        if targets_here and diseases_here:
            relation_type = _find_trigger(sentence_text, TARGET_DISEASE_TRIGGERS)
            if relation_type:
                for target in targets_here:
                    for disease in diseases_here:
                        _add_relation(target, relation_type, disease)

        # Drug -> Disease relations -- ONLY direct clinical language,
        # e.g. "Metformin is prescribed for type 2 diabetes"
        if drugs_here and diseases_here:
            relation_type = _find_trigger(sentence_text, DRUG_DISEASE_TRIGGERS)
            if relation_type:
                for drug in drugs_here:
                    for disease in diseases_here:
                        _add_relation(drug, relation_type, disease)

    return {
        "drugs": [{"name": d} for d in drugs],
        "diseases": [{"name": d} for d in diseases],
        "targets": [{"name": t} for t in targets],
        "relations": relations
    }


def _is_plausible_entity_name(name: str, max_words: int = 6) -> bool:
    """
    Real drug/disease/target names are almost always short (a handful of
    words at most). When the model occasionally grabs an entire clause
    or sentence fragment as an "entity" -- which does happen, especially
    on complex real-world abstracts -- this is a cheap, effective filter
    to catch it before it pollutes your graph.
    """
    word_count = len(name.split())
    return word_count <= max_words


def _dedupe_entities(entity_tuples):
    """Takes a list of (name, start_char, end_char) tuples and returns
    just the unique names, case-insensitively, preserving first-seen
    casing (so "AMPK" doesn't get duplicated as "ampk"). Also filters
    out implausibly long "entities" that are almost certainly NER
    mistakes rather than real names."""
    seen = {}
    for name, _, _ in entity_tuples:
        if not _is_plausible_entity_name(name):
            continue
        key = name.lower()
        if key not in seen:
            seen[key] = name
    return list(seen.values())

GENERIC_SUFFIXES = ("-based", "-derived", "-related", "-associated", "-mediated", "-induced")

def _is_plausible_entity_name(name: str, max_words: int = 6) -> bool:
    word_count = len(name.split())
    if word_count > max_words:
        return False
    if name.lower().endswith(GENERIC_SUFFIXES):
        return False
    return True
if __name__ == "__main__":
    sample_abstract = (
        "Metformin, a first-line treatment for type 2 diabetes, has been "
        "shown to activate AMPK signaling. Recent studies suggest AMPK "
        "activation may play a role in regulating ovarian follicle "
        "development, implicating this pathway in polycystic ovary "
        "syndrome (PCOS) pathophysiology."
    )

    import json
    result = extract_entities(sample_abstract)
    print(json.dumps(result, indent=2))
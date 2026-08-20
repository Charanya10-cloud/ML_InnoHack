# disease_normalizer.py
#
# Same job as drug_normalizer.py, but for diseases -- and disease names
# have a DIFFERENT common problem: abbreviations. "PCOS" and "polycystic
# ovary syndrome" are the exact same disease, but as plain text they
# look completely unrelated. This is exactly the bug you saw earlier in
# your real extraction output (test_001 had both as separate entries).

import re

# Abbreviation/synonym mapping. Key = lowercase alias, Value = the ONE
# canonical name we want everywhere downstream.
#
# Build this out as you go -- every time you notice a new abbreviation
# in your real ingested abstracts, add it here.
DISEASE_SYNONYMS = {
    "pcos": "Polycystic Ovary Syndrome",
    "polycystic ovary syndrome": "Polycystic Ovary Syndrome",
    "polycystic ovarian syndrome": "Polycystic Ovary Syndrome",

    "t2d": "Type 2 Diabetes",
    "type 2 diabetes": "Type 2 Diabetes",
    "type ii diabetes": "Type 2 Diabetes",
    "diabetes": "Type 2 Diabetes",  # NOTE: only safe because our focus
                                      # areas don't currently involve
                                      # Type 1 diabetes -- revisit this
                                      # entry if that changes.

    "ad": "Alzheimer's Disease",
    "alzheimer's disease": "Alzheimer's Disease",
    "alzheimers disease": "Alzheimer's Disease",
    "alzheimer disease": "Alzheimer's Disease",

    "ra": "Rheumatoid Arthritis",
    "rheumatoid arthritis": "Rheumatoid Arthritis",

    "hyperlipidemia": "Hyperlipidemia",
    "hyperlipidaemia": "Hyperlipidemia",  # British spelling variant
}


def _clean_whitespace(name: str) -> str:
    """Collapses multiple spaces and trims leading/trailing whitespace."""
    return re.sub(r"\s+", " ", name).strip()


def normalize_disease_name(raw_name: str) -> str:
    """
    Takes a raw disease name string, returns the canonical version.

    Example:
        normalize_disease_name("PCOS")                      -> "Polycystic Ovary Syndrome"
        normalize_disease_name("polycystic ovary syndrome")  -> "Polycystic Ovary Syndrome"
        normalize_disease_name("Some Rare Disease")           -> "Some Rare Disease" (unchanged,
                                                                   not in our map)
    """
    if not raw_name:
        return raw_name

    cleaned = _clean_whitespace(raw_name)

    lookup_key = cleaned.lower()
    if lookup_key in DISEASE_SYNONYMS:
        return DISEASE_SYNONYMS[lookup_key]

    # Not a known synonym -- return cleaned version, title-cased for
    # consistency, even though we can't guarantee it matches another
    # variant we haven't seen yet.
    return cleaned.title() if cleaned.islower() else cleaned


if __name__ == "__main__":
    test_names = [
        "PCOS",
        "polycystic ovary syndrome",
        "Polycystic Ovarian Syndrome",
        "type 2 diabetes",
        "Alzheimer's disease",
        "rheumatoid arthritis",
        "Some Rare Disease",
    ]

    for name in test_names:
        print(f"{name!r:35} -> {normalize_disease_name(name)!r}")
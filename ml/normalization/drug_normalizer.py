# drug_normalizer.py
#
# Job: take a messy, raw drug name as extracted from text (e.g. "Metformin
# HCl", "metformin", "Metformin hydrochloride") and turn it into ONE
# consistent, canonical name ("Metformin") every time.
#
# Why this matters: without this step, your graph would treat "Metformin"
# and "metformin HCl" as two totally different drugs, which would split
# your evidence in half and weaken every signal that depends on it.

import re

# Common salt/formulation suffixes that show up attached to drug names
# but don't change WHICH drug it is. We strip these off during cleanup.
# Add to this list as you encounter more in your real data.
SALT_SUFFIXES = [
    "hydrochloride",
    "hcl",
    "sodium",
    "sulfate",
    "sulphate",
    "citrate",
    "phosphate",
    "tablets",
    "tablet",
    "injection",
    "capsules",
    "capsule",
]

# Known synonym/alias mapping. Key = lowercase alias, Value = the ONE
# canonical name we want to use everywhere downstream.
#
# This is a hardcoded, hand-curated list -- deliberately simple. For a
# hackathon scoped to 2-3 disease areas, this is genuinely the right
# approach: you'll add entries here as you notice aliases in your real
# ingested data, focused on the drugs that actually show up.
DRUG_SYNONYMS = {
    "metformin": "Metformin",
    "metformin hcl": "Metformin",
    "rapamycin": "Rapamycin",
    "sirolimus": "Rapamycin",  # sirolimus is the generic/scientific name for Rapamycin
    "statins": "Statins",
    "statin": "Statins",
    "atorvastatin": "Atorvastatin",
    "simvastatin": "Simvastatin",
}


def _strip_salt_suffixes(name: str) -> str:
    """Removes common salt/formulation words from the end of a drug name.
    e.g. 'Metformin Hydrochloride' -> 'Metformin'"""
    cleaned = name
    for suffix in SALT_SUFFIXES:
        # \b means "word boundary" -- this makes sure we only match whole
        # words, so we don't accidentally chop letters out of the middle
        # of an unrelated word.
        pattern = r"\b" + re.escape(suffix) + r"\b"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # Clean up any extra whitespace left behind after removing words
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_drug_name(raw_name: str) -> str:
    """
    Takes a raw drug name string, returns the canonical version.

    Example:
        normalize_drug_name("Metformin HCl")  -> "Metformin"
        normalize_drug_name("sirolimus")       -> "Rapamycin"
        normalize_drug_name("Aspirin")         -> "Aspirin"  (unchanged,
                                                    not in our synonym map,
                                                    but still cleaned up)
    """
    if not raw_name:
        return raw_name

    # Step 1: basic cleanup -- remove salt suffixes and extra whitespace
    cleaned = _strip_salt_suffixes(raw_name.strip())

    # Step 2: check our synonym dictionary, case-insensitively
    lookup_key = cleaned.lower()
    if lookup_key in DRUG_SYNONYMS:
        return DRUG_SYNONYMS[lookup_key]

    # Step 3: not a known synonym -- return the cleaned version, title-cased
    # so at least casing is consistent even for drugs we haven't mapped yet.
    return cleaned.title() if cleaned.islower() else cleaned


if __name__ == "__main__":
    # Quick manual test -- run this file directly to sanity check
    test_names = [
        "Metformin HCl",
        "metformin",
        "sirolimus",
        "Rapamycin",
        "STATINS",
        "Aspirin",
    ]

    for name in test_names:
        print(f"{name!r:25} -> {normalize_drug_name(name)!r}")
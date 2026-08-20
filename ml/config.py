# config.py
# Central place for settings.

# Two local models now, not one:
# - CHEM_DISEASE_MODEL finds drugs (CHEMICAL) and diseases (DISEASE)
# - TARGET_MODEL finds genes/proteins/pathways (GENE_OR_GENE_PRODUCT),
#   which act as the "middle step" connecting a drug to a disease.
CHEM_DISEASE_MODEL_NAME = "en_ner_bc5cdr_md"
TARGET_MODEL_NAME = "en_ner_bionlp13cg_md"

OUTPUT_DIR = "output"

# --- Integration settings ---
import os
from dotenv import load_dotenv

# Reads ml/.env (if it exists) and loads its values as environment
# variables -- this is how DATABASE_URL below picks up your REAL Neon
# connection string instead of falling back to the localhost default,
# which has no server running there.
load_dotenv()

# Must match Backend's database so ML can read real ingested documents
# directly from raw_docs. Set the REAL value in ml/.env (see .env.example) --
# never hardcode a real connection string directly in this file.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://repurpose:repurpose@localhost:5432/repurpose"
)

# Where Backend's FastAPI app is running -- used to POST finished signals
# to POST /signals/ingest.
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

# Trigger words are now split by WHICH pair of entity types they apply
# to. This fixes the earlier bug where "Metformin activates AMPK" was
# wrongly read as "Metformin activates diabetes" -- now a trigger only
# fires for the correct pair type.

# Drug -> Target relations (e.g. "Metformin activates AMPK")
DRUG_TARGET_TRIGGERS = {
    "activat": "ACTIVATES",
    "inhibit": "INHIBITS",
    "target": "TARGETS",
    "regulat": "TARGETS",
    "effect": "MODULATES",   # catches "effect on" / "effects on" -- softer
                              # language than activate/inhibit, so we use a
                              # more honest, less specific relation type
    "modulat": "MODULATES",
}

# Target -> Disease relations (e.g. "AMPK is implicated in PCOS")
TARGET_DISEASE_TRIGGERS = {
    "implicat": "IMPLICATED_IN",
    "associat": "IMPLICATED_IN",
    "role in": "IMPLICATED_IN",
}

# Drug -> Disease relations -- ONLY for direct clinical usage language,
# not mechanism language. This is legitimate on its own (e.g. "Metformin
# is prescribed for type 2 diabetes" is a real, direct relation).
DRUG_DISEASE_TRIGGERS = {
    "treat": "STUDIED_FOR",
    "prescrib": "STUDIED_FOR",
    "first-line": "STUDIED_FOR",
}

# Substances the CHEMICAL model tends to mislabel as "drugs" when they're
# actually endogenous biomarkers or pathological features of a disease --
# NOT something you'd ever repurpose as a treatment. Real example that
# triggered this list: "Amyloid Plaques" was extracted as a drug, when
# it's literally a hallmark pathological feature OF Alzheimer's disease.
# A signal like "Amyloid Plaques treats X" is nonsensical and undermines
# trust in the whole system if it shows up in a demo.
#
# Build this out as you spot more in real data -- same hand-curated
# approach as DRUG_SYNONYMS.
DRUG_BLOCKLIST = {
    "amyloid plaques",
    "amyloid-beta",
    "amyloid beta",
    "amyloid",
    "cholesterol",
    "glucose",
    "cortisol",
}
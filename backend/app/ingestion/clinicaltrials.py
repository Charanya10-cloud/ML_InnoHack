"""Fetch trial records from ClinicalTrials.gov API v2 for a disease-area term.

Docs: https://clinicaltrials.gov/data-api/api
These give real-world "drug X is being trialed for disease Y" signals that
complement literature-derived mechanism relations from bioRxiv/PubMed.
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_page(term: str, page_token: str | None, page_size: int) -> dict:
    params = {
        "query.cond": term,
        "pageSize": page_size,
        "fields": ",".join(
            [
                "NCTId",
                "BriefTitle",
                "BriefSummary",
                "InterventionName",
                "Condition",
                "StartDate",
            ]
        ),
    }
    if page_token:
        params["pageToken"] = page_token

    resp = httpx.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_clinicaltrials_docs(disease_area: str, max_docs: int = 100) -> list[dict]:
    docs: list[dict] = []
    page_token = None

    while len(docs) < max_docs:
        page = _fetch_page(disease_area, page_token, page_size=min(100, max_docs - len(docs)))
        studies = page.get("studies", [])
        if not studies:
            break

        for study in studies:
            protocol = study.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            desc = protocol.get("descriptionModule", {})
            arms = protocol.get("armsInterventionsModule", {})
            interventions = arms.get("interventions", [])
            drug_names = ", ".join(i.get("name", "") for i in interventions if i.get("name"))

            nct_id = ident.get("nctId", "")
            title = ident.get("briefTitle", "")
            summary = desc.get("briefSummary", "")

            docs.append(
                {
                    "source": "clinicaltrials",
                    "source_id": nct_id,
                    "title": title,
                    "abstract": f"{summary}\n\nInterventions: {drug_names}".strip(),
                    "url": f"https://clinicaltrials.gov/study/{nct_id}",
                    "published_at": None,
                    "disease_area": disease_area,
                    "raw_metadata": {"interventions": drug_names},
                }
            )

        page_token = page.get("nextPageToken")
        if not page_token:
            break

    return docs

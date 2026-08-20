"""Fetch PubMed abstracts for a disease-area search term via NCBI E-utilities
(esearch -> efetch). Free, but rate-limited to 3 req/s without an API key,
10 req/s with one (set NCBI_API_KEY / NCBI_EMAIL in .env).
"""

import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _auth_params() -> dict:
    settings = get_settings()
    params = {}
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _esearch(term: str, retmax: int) -> list[str]:
    params = {
        "db": "pubmed",
        "term": f"{term} AND (drug repurposing OR repositioning OR mechanism)",
        "retmax": retmax,
        "retmode": "json",
        **_auth_params(),
    }
    resp = httpx.get(ESEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("esearchresult", {}).get("idlist", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _efetch(pmids: list[str]) -> str:
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        **_auth_params(),
    }
    resp = httpx.get(EFETCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.text


def _parse_articles(xml_text: str, disease_area: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    docs = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        abstract_el = article.find(".//AbstractText")
        date_el = article.find(".//PubDate/Year")

        pmid = pmid_el.text if pmid_el is not None else None
        if not pmid:
            continue

        docs.append(
            {
                "source": "pubmed",
                "source_id": pmid,
                "title": (title_el.text or "") if title_el is not None else "",
                "abstract": (abstract_el.text or "") if abstract_el is not None else "",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "published_at": f"{date_el.text}-01-01" if date_el is not None else None,
                "disease_area": disease_area,
                "raw_metadata": {},
            }
        )
    return docs


def fetch_pubmed_docs(disease_area: str, max_docs: int = 100) -> list[dict]:
    pmids = _esearch(disease_area, retmax=max_docs)
    if not pmids:
        return []

    docs: list[dict] = []
    batch_size = 50
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        xml_text = _efetch(batch)
        docs.extend(_parse_articles(xml_text, disease_area))

    return docs

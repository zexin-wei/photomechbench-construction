"""Mechanism-oriented literature discovery and local document identity checks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Protocol

import requests
from pypdf import PdfReader

from .mechanism_profiles import load_mechanism_profile
from .vocabulary import OFFICIAL_MECHANISMS

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s<>\]\[\"'`{}|\\]+", re.IGNORECASE)
SUPPLEMENTARY_PATTERNS = (
    re.compile(r"supporting information", re.IGNORECASE),
    re.compile(r"supplementary (?:information|material|data)", re.IGNORECASE),
    re.compile(r"electronic supplementary information", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class SearchHit:
    retrieval_mechanism: str
    query: str
    title: str
    url: str
    excerpt: str
    visible_doi: str | None
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DoiRecord:
    doi: str
    title: str
    retrieval_mechanisms: tuple[str, ...]
    source_urls: tuple[str, ...]
    resolution_method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SearchClient(Protocol):
    def search(self, *, query: str, max_results: int, search_depth: str) -> list[dict[str, Any]]:
        ...


class TavilyClientAdapter:
    """Adapter around an injected Tavily SDK client without storing its key."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def search(self, *, query: str, max_results: int, search_depth: str) -> list[dict[str, Any]]:
        response = self._client.search(query=query, max_results=max_results, search_depth=search_depth)
        rows = response.get("results", []) if isinstance(response, dict) else []
        return [row for row in rows if isinstance(row, dict)]


class TavilyRestClient:
    """Minimal Tavily Search REST client using the package's requests dependency."""

    def __init__(
        self,
        api_key: str,
        *,
        session: requests.Session | None = None,
        base_url: str = "https://api.tavily.com",
        timeout: float = 60.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Tavily API key must not be empty.")
        self._api_key = api_key
        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def search(self, *, query: str, max_results: int, search_depth: str) -> list[dict[str, Any]]:
        response = self._session.post(
            f"{self._base_url}/search",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={"query": query, "max_results": max_results, "search_depth": search_depth},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("results", []) if isinstance(payload, dict) else []
        return [row for row in rows if isinstance(row, dict)]


def run_literature_retrieval(
    mechanism: str,
    *,
    client: SearchClient,
    output_dir: Path,
    max_results: int = 20,
    search_depth: str = "advanced",
    max_queries: int | None = None,
    resolve_unlisted_dois: bool = True,
    crossref_session: requests.Session | None = None,
) -> dict[str, Any]:
    """Run and persist one mechanism-oriented retrieval batch."""
    profile = load_mechanism_profile(mechanism)
    queries = list(profile["queries"])
    if max_queries is not None:
        if max_queries < 1:
            raise ValueError("max_queries must be at least 1.")
        queries = queries[:max_queries]
    if max_results < 1:
        raise ValueError("max_results must be at least 1.")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "queries.json",
        {
            "mechanism": mechanism,
            "search_depth": search_depth,
            "max_results_per_query": max_results,
            "queries": queries,
        },
    )

    hits: list[SearchHit] = []
    query_reports: list[dict[str, Any]] = []
    query_result_dir = output_dir / "query_results"
    for query_index, query in enumerate(queries, start=1):
        report: dict[str, Any] = {
            "query_index": query_index,
            "mechanism": mechanism,
            "query": query,
            "success": False,
            "results": [],
        }
        try:
            rows = client.search(query=query, max_results=max_results, search_depth=search_depth)
            report["success"] = True
            report["results"] = rows
            for rank, row in enumerate(rows, start=1):
                title = str(row.get("title") or "").strip()
                url = str(row.get("url") or "").strip()
                excerpt = str(row.get("content") or row.get("snippet") or "").strip()
                hits.append(
                    SearchHit(
                        retrieval_mechanism=mechanism,
                        query=query,
                        title=title,
                        url=url,
                        excerpt=excerpt,
                        visible_doi=extract_first_doi(" ".join((title, url, excerpt))),
                        rank=rank,
                    )
                )
        except Exception as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
        query_reports.append(report)
        _write_json(query_result_dir / f"{query_index:03d}.json", report)
        _write_json(output_dir / "search_hits.json", {"hits": [hit.to_dict() for hit in hits]})

    records, unresolved = resolve_hits(
        hits,
        crossref_session=crossref_session,
        match_unresolved_titles=resolve_unlisted_dois,
    )
    _write_json(output_dir / "resolved_doi_records.json", {"records": [record.to_dict() for record in records]})
    _write_json(output_dir / "unresolved_hits.json", {"hits": unresolved})
    summary = {
        "mechanism": mechanism,
        "query_count": len(queries),
        "successful_query_count": sum(bool(report["success"]) for report in query_reports),
        "failed_query_count": sum(not bool(report["success"]) for report in query_reports),
        "search_hit_count": len(hits),
        "resolved_doi_count": len(records),
        "unresolved_hit_count": len(unresolved),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output_dir / "retrieval_summary.json", summary)
    return summary


def search_mechanism(
    mechanism: str,
    *,
    client: SearchClient,
    max_results: int = 20,
    search_depth: str = "advanced",
) -> list[SearchHit]:
    """Run every query in one mechanism profile and preserve retrieval provenance."""
    profile = load_mechanism_profile(mechanism)
    hits: list[SearchHit] = []
    for query in profile["queries"]:
        rows = client.search(query=query, max_results=max_results, search_depth=search_depth)
        for rank, row in enumerate(rows, start=1):
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            excerpt = str(row.get("content") or row.get("snippet") or "").strip()
            hits.append(
                SearchHit(
                    retrieval_mechanism=mechanism,
                    query=query,
                    title=title,
                    url=url,
                    excerpt=excerpt,
                    visible_doi=extract_first_doi(" ".join((title, url, excerpt))),
                    rank=rank,
                )
            )
    return hits


def resolve_hits(
    hits: Iterable[SearchHit],
    *,
    crossref_session: requests.Session | None = None,
    min_title_score: float = 0.90,
    timeout: float = 30.0,
    match_unresolved_titles: bool = True,
) -> tuple[list[DoiRecord], list[dict[str, Any]]]:
    """Resolve visible DOI values first, then optionally match unresolved titles."""
    session = crossref_session or requests.Session()
    resolved: list[tuple[SearchHit, str, str]] = []
    unresolved: list[dict[str, Any]] = []
    for hit in hits:
        doi = normalize_doi(hit.visible_doi)
        method = "visible_doi"
        if not doi and hit.title and match_unresolved_titles:
            match = crossref_match_title(hit.title, session=session, timeout=timeout)
            if match and match[1] >= min_title_score:
                doi = match[0]
                method = "crossref_title_match"
        if doi:
            resolved.append((hit, doi, method))
        else:
            unresolved.append({**hit.to_dict(), "status": "doi_unresolved"})

    grouped: dict[str, list[tuple[SearchHit, str]]] = {}
    for hit, doi, method in resolved:
        grouped.setdefault(doi, []).append((hit, method))
    records: list[DoiRecord] = []
    for doi, items in sorted(grouped.items()):
        titles = [hit.title for hit, _ in items if hit.title]
        records.append(
            DoiRecord(
                doi=doi,
                title=max(titles, key=len) if titles else "",
                retrieval_mechanisms=tuple(sorted({hit.retrieval_mechanism for hit, _ in items})),
                source_urls=tuple(sorted({hit.url for hit, _ in items if hit.url})),
                resolution_method="visible_doi" if any(method == "visible_doi" for _, method in items) else "crossref_title_match",
            )
        )
    return records, unresolved


def targeted_crossref_search(
    *,
    mechanism: str,
    session: requests.Session | None = None,
    rows_per_query: int = 20,
    timeout: float = 30.0,
) -> list[DoiRecord]:
    """Supplement an underrepresented mechanism through bibliographic search."""
    if mechanism not in OFFICIAL_MECHANISMS:
        raise ValueError(f"Unknown mechanism: {mechanism}")
    session = session or requests.Session()
    profile = load_mechanism_profile(mechanism)
    found: dict[str, DoiRecord] = {}
    for query in profile["queries"]:
        response = session.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query, "rows": rows_per_query},
            timeout=timeout,
        )
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        for item in items:
            if not isinstance(item, dict):
                continue
            doi = normalize_doi(item.get("DOI"))
            if not doi:
                continue
            titles = item.get("title") or []
            title = str(titles[0]) if isinstance(titles, list) and titles else ""
            found.setdefault(
                doi,
                DoiRecord(
                    doi=doi,
                    title=title,
                    retrieval_mechanisms=(mechanism,),
                    source_urls=(),
                    resolution_method="crossref_targeted_search",
                ),
            )
    return [found[key] for key in sorted(found)]


def crossref_match_title(
    title: str,
    *,
    session: requests.Session,
    timeout: float = 30.0,
) -> tuple[str, float, str] | None:
    response = session.get(
        "https://api.crossref.org/works",
        params={"query.title": title, "rows": 3},
        timeout=timeout,
    )
    response.raise_for_status()
    best: tuple[str, float, str] | None = None
    for item in response.json().get("message", {}).get("items", []):
        if not isinstance(item, dict):
            continue
        doi = normalize_doi(item.get("DOI"))
        titles = item.get("title") or []
        candidate_title = str(titles[0]) if isinstance(titles, list) and titles else ""
        if not doi or not candidate_title:
            continue
        score = title_similarity(title, candidate_title)
        if best is None or score > best[1]:
            best = (doi, score, candidate_title)
    return best


def verify_pdf_identity(
    path: Path,
    *,
    expected_doi: str,
    expected_title: str = "",
    max_pages: int = 3,
    min_title_score: float = 0.82,
) -> dict[str, Any]:
    """Read PDF metadata/early pages and classify DOI, title, and supplement status."""
    expected_doi = normalize_doi(expected_doi)
    report: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256(path),
        "expected_doi": expected_doi,
        "expected_title": expected_title,
        "pdf_readable": False,
        "page_count": None,
        "found_dois": [],
        "doi_matches": False,
        "title_score": None,
        "supplementary_likely": None,
        "status": "unreadable",
        "error": None,
    }
    try:
        reader = PdfReader(str(path))
        report["page_count"] = len(reader.pages)
        metadata_title = str((reader.metadata or {}).get("/Title") or "").strip()
        text_parts: list[str] = []
        for page in reader.pages[:max_pages]:
            text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts)
        report["pdf_readable"] = bool(text.strip())
        found = sorted({normalize_doi(item) for item in DOI_PATTERN.findall(text) if normalize_doi(item)})
        report["found_dois"] = found
        report["doi_matches"] = bool(expected_doi and expected_doi in found)
        title_source = metadata_title or _first_nonempty_line(text)
        report["observed_title"] = title_source
        if expected_title and title_source:
            report["title_score"] = round(title_similarity(expected_title, title_source), 4)
        combined = "\n".join((path.name, metadata_title, text[:5000]))
        supplementary = any(pattern.search(combined) for pattern in SUPPLEMENTARY_PATTERNS)
        report["supplementary_likely"] = supplementary
        title_ok = report["title_score"] is None or report["title_score"] >= min_title_score
        if supplementary:
            report["status"] = "supplementary_file"
        elif expected_doi and found and not report["doi_matches"]:
            report["status"] = "identity_mismatch"
        elif not title_ok:
            report["status"] = "identity_mismatch"
        elif not report["pdf_readable"]:
            report["status"] = "text_unreadable"
        else:
            report["status"] = "main_article_candidate"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def download_pdf(
    url: str,
    *,
    destination: Path,
    session: requests.Session | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Download one explicitly supplied accessible PDF URL."""
    session = session or requests.Session()
    response = session.get(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF"):
        raise ValueError("Downloaded content is not a PDF.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return {
        "url": url,
        "destination": str(destination),
        "bytes": len(content),
        "sha256": sha256(destination),
    }


def extract_first_doi(text: str) -> str | None:
    match = DOI_PATTERN.search(text or "")
    return normalize_doi(match.group(0)) if match else None


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi\s*:\s*", "", text)
    return text.strip().rstrip(".,;:)")


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_nonempty_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

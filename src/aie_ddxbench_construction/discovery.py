"""Automatic discovery of PDF inputs and parsed-paper metadata."""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Any

_DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
_TITLE_EXCLUSIONS = {
    "abstract",
    "acknowledgements",
    "acknowledgments",
    "author contributions",
    "conflicts of interest",
    "contents",
    "introduction",
    "references",
    "supporting information",
}


def discover_pdf_rows(input_path: Path) -> list[dict[str, Any]]:
    """Return deterministic internal paper rows for one PDF or a PDF directory."""
    input_path = input_path.resolve()
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file must be a PDF: {input_path}")
        paths = [input_path]
    elif input_path.is_dir():
        paths = sorted(
            (path.resolve() for path in input_path.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"),
            key=lambda path: str(path).lower(),
        )
    else:
        raise FileNotFoundError(f"Input PDF or directory does not exist: {input_path}")
    if not paths:
        raise ValueError(f"No PDF files were found under: {input_path}")

    rows: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for path in paths:
        digest = file_sha256(path)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        rows.append(
            {
                "paper_id": f"{_identifier_part(path.stem)}_{digest[:8].upper()}",
                "doi": "",
                "title": "",
                "pdf_name": path.name,
                "source_pdf": str(path),
                "source_pdf_sha256": digest,
                "metadata_status": "pending_mineru_parse",
            }
        )
    return rows


def discover_parsed_metadata(source_md: Path) -> dict[str, str]:
    """Extract conservative DOI and title candidates from parsed Markdown."""
    text = source_md.read_text(encoding="utf-8", errors="replace")
    doi = ""
    match = _DOI_PATTERN.search(text[:80_000])
    if match:
        doi = normalize_doi(match.group(0))

    lines = text[:30_000].splitlines()[:160]
    title = _first_title_candidate(line for line in lines if re.match(r"^\s{0,3}#{1,6}\s+", line))
    if not title:
        title = _first_title_candidate(iter(lines))
    return {"doi": doi, "title": title}


def _first_title_candidate(lines: Any) -> str:
    for raw_line in lines:
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw_line).strip()
        line = html.unescape(re.sub(r"</?[^>]+>", "", line))
        line = re.sub(r"\s+", " ", line)
        if (
            20 <= len(line) <= 350
            and line.lower().rstrip(":") not in _TITLE_EXCLUSIONS
            and "view article online" not in line.lower()
            and not line.lower().startswith(("cite this:", "received ", "accepted "))
            and not line.startswith(("!", "|", "<", "http://", "https://"))
            and not _DOI_PATTERN.fullmatch(line)
        ):
            return line
    return ""


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", text, flags=re.IGNORECASE)
    return text.rstrip(".,;:)]}>").lower()


def is_valid_doi(value: Any) -> bool:
    normalized = normalize_doi(value)
    return _DOI_PATTERN.fullmatch(normalized) is not None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identifier_part(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").upper()
    return text[:48] or "PAPER"

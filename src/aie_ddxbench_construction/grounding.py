"""Deterministic source-grounding checks for v0.4 evidence quotations.

The module locates each ``paper_quote`` in parsed source Markdown using exact
and advisory fuzzy matching. It does not call models, invoke RDKit, or modify
case JSON.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any


def assess_paper_quote_grounding(case: dict, source_markdown: str, *, fuzzy_threshold: float = 0.82) -> dict:
    """Return exact and fuzzy source matches for every evidence quotation.

    This helper reports grounding status. The local gate decides whether a
    missing quote is blocking and whether a fuzzy-only match is a warning.
    """
    source_normalized = _normalize_text(source_markdown)
    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for index, unit in enumerate(_evidence_units(case)):
        evidence_id = unit.get("evidence_id")
        quote = str(unit.get("paper_quote", "")).strip()
        source_span = unit.get("source_span")
        path = f"hidden_reference.reference_evidence_units[{index}].paper_quote"
        if not quote:
            continue

        quote_normalized = _normalize_text(quote)
        exact_match = bool(quote_normalized and quote_normalized in source_normalized)
        best_ratio = 1.0 if exact_match else _best_fuzzy_ratio(quote_normalized, source_normalized)
        status = "exact_match" if exact_match else "fuzzy_match" if best_ratio >= fuzzy_threshold else "not_found"
        check = {
            "evidence_id": evidence_id,
            "path": path,
            "status": status,
            "exact_match": exact_match,
            "fuzzy_ratio": round(best_ratio, 3),
            "source_location": source_span,
        }
        checks.append(check)
        if status != "exact_match":
            warnings.append(
                {
                    "issue_type": "paper_quote_fuzzy_match_only" if status == "fuzzy_match" else "paper_quote_not_found",
                    "path": path,
                    "evidence_id": evidence_id,
                    "message": "paper_quote was not found as a continuous exact span in source_page_aware.md.",
                    "quote": quote,
                    "source_location": source_span,
                    "fuzzy_ratio": round(best_ratio, 3),
                }
            )

    return {
        "check_name": "paper_quote_grounding",
        "checked": True,
        "warning_count": len(warnings),
        "checks": checks,
        "warnings": warnings,
    }


def _best_fuzzy_ratio(quote: str, source: str) -> float:
    if not quote or not source:
        return 0.0
    if len(source) <= len(quote):
        return SequenceMatcher(None, quote, source).ratio()
    window_size = max(len(quote), 80)
    step = max(window_size // 4, 40)
    best = 0.0
    for start in range(0, max(len(source) - window_size + 1, 1), step):
        window = source[start : start + window_size]
        best = max(best, SequenceMatcher(None, quote, window).ratio())
        if best >= 0.98:
            break
    return best


def _normalize_text(value: str) -> str:
    value = value.replace("...", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip().lower()


def _evidence_units(case: dict) -> list[dict[str, Any]]:
    units = case.get("hidden_reference", {}).get("reference_evidence_units", [])
    return [unit for unit in units if isinstance(unit, dict)] if isinstance(units, list) else []

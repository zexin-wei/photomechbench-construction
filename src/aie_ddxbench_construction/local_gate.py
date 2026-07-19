"""Read-only deterministic local gate for v0.4 case candidates.

The gate checks structure-sidecar consistency, the SMILES-only public-input
boundary, schema and identifier links, placeholder text, cross-candidate
contamination, and source grounding of paper quotations. It may invoke RDKit
through sidecar checks but never calls a language model or writes case JSON.
"""

from __future__ import annotations

import re
from typing import Any

from .grounding import assess_paper_quote_grounding
from .locked_structure import check_locked_structure
from .public_input import check_smiles_only_public_input
from .vocabulary import FINAL_SYNTHESIS_MECHANISM, OFFICIAL_MECHANISM_SET

SPECIAL_DIAGNOSIS_MECHANISM_SET = {FINAL_SYNTHESIS_MECHANISM}


TOP_LEVEL_KEYS = {"case_id", "version", "track", "public_input", "hidden_reference"}
HIDDEN_REFERENCE_KEYS = {"source_article", "reference_evidence_units", "reference_diagnosis_units"}
EVIDENCE_REQUIRED_KEYS = {
    "evidence_id",
    "claim",
    "mechanistic_interpretation",
    "mechanism_links",
    "evidence_accessibility",
    "source_span",
    "paper_quote",
}
DIAGNOSIS_REQUIRED_KEYS = {
    "diagnosis_id",
    "mechanism",
    "context",
    "reference_status",
    "expert_conclusion",
    "supporting_evidence_ids",
    "diagnosis_role",
}
ALLOWED_REFERENCE_STATUS = {"supported", "weakened_or_rejected", "underdetermined"}
FORBIDDEN_KEYS = {
    "evaluation",
    "evidence_trace",
    "curation_status",
    "diagnostic_targets",
    "expected_final_profile",
    "known_failure_modes",
    "candidate_hypotheses",
    "visible_observations",
    "article_context",
    "reported_claim",
    "structure_resolution_report",
}
FORBIDDEN_KEY_SUFFIXES = ("_structure_adjudication", "_structure_review")
PLACEHOLDER_VALUES = {"", "todo", "tbd", "placeholder", "unknown", "n/a", "not specified"}
MOJIBAKE_PATTERNS = (
    re.compile(r"锟"),
    re.compile(r"脙|脗|茂驴陆|芒鈧"),
    re.compile(r"\ufffd"),
)
EVIDENCE_ID_PATTERN = re.compile(r"^[EN][0-9]+$")
DIAGNOSIS_ID_PATTERN = re.compile(r"^D[0-9]{2}$")
COMPARISON_OR_PRODUCT_PATTERN = re.compile(
    r"\b("
    r"background|comparison|compare[sd]?|relative|than|between|interconversion|"
    r"product|produced|yield(?:s|ed)?|isomeriz(?:e|es|ed|ation)|convert(?:s|ed|ing)?|"
    r"ratio|branch(?:ing|es)?"
    r")\b",
    re.IGNORECASE,
)


def run_local_gate(
    *,
    case: Any,
    source_markdown: str,
    locked_structure: Any,
    allow_provisional_structure: bool = False,
) -> dict[str, Any]:
    """Run every deterministic check for one v0.4 case candidate.

    Schema errors, public-SMILES mismatch, invalid sidecars, RDKit failure,
    missing source quotations, and cross-candidate contamination are blocking.
    The caller is responsible for writing the returned report.
    """
    blocking_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    check_reports: dict[str, Any] = {}

    sidecar_report = check_locked_structure(
        locked_structure,
        allow_provisional_structure=allow_provisional_structure,
    )
    check_reports["locked_structure"] = sidecar_report
    blocking_issues.extend(_tag(sidecar_report.get("blocking_issues", []), "locked_structure"))
    warnings.extend(_tag(sidecar_report.get("warnings", []), "locked_structure"))

    locked_smiles = sidecar_report.get("locked_smiles")
    public_report = check_smiles_only_public_input(case, locked_smiles if isinstance(locked_smiles, str) else None)
    check_reports["smiles_public_input"] = public_report
    blocking_issues.extend(_tag(public_report.get("blocking_issues", []), "smiles_public_input"))
    warnings.extend(_tag(public_report.get("warnings", []), "smiles_public_input"))

    schema_report = _check_schema_and_links(case)
    check_reports["schema_and_links"] = schema_report
    blocking_issues.extend(_tag(schema_report["blocking_issues"], "schema_and_links"))
    warnings.extend(_tag(schema_report["warnings"], "schema_and_links"))

    quality_report = _check_text_quality(case)
    check_reports["text_quality"] = quality_report
    blocking_issues.extend(_tag(quality_report["blocking_issues"], "text_quality"))
    warnings.extend(_tag(quality_report["warnings"], "text_quality"))

    cross_candidate_report = _check_cross_candidate_identity(case, locked_smiles if isinstance(locked_smiles, str) else None)
    check_reports["cross_candidate_identity"] = cross_candidate_report
    blocking_issues.extend(_tag(cross_candidate_report["blocking_issues"], "cross_candidate_identity"))
    warnings.extend(_tag(cross_candidate_report["warnings"], "cross_candidate_identity"))

    grounding_report = assess_paper_quote_grounding(case if isinstance(case, dict) else {}, source_markdown)
    check_reports["paper_quote_grounding"] = grounding_report
    for warning in grounding_report.get("warnings", []):
        issue_type = warning.get("issue_type")
        if issue_type == "paper_quote_not_found":
            blocking_issues.append({**warning, "stage": "paper_quote_grounding"})
        else:
            warnings.append({**warning, "stage": "paper_quote_grounding"})

    return {
        "report_name": "local_gate_report",
        "stage": "raw_case_validation",
        "gate_passed": not blocking_issues,
        "blocking_issue_count": len(blocking_issues),
        "warning_count": len(warnings),
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "summary": {
            "read_only": True,
            "json_repaired": False,
            "official_json_written": False,
            "locked_smiles": locked_smiles,
            "final_structure_status": sidecar_report.get("final_structure_status"),
        },
        "checks": check_reports,
    }


def render_local_gate_markdown(report: dict[str, Any]) -> str:
    """Render a concise Markdown summary of a local-gate report."""
    lines = [
        "# Local gate report",
        "",
        f"- gate_passed: {report.get('gate_passed')}",
        f"- blocking_issue_count: {report.get('blocking_issue_count')}",
        f"- warning_count: {report.get('warning_count')}",
        f"- read_only: {report.get('summary', {}).get('read_only')}",
        f"- official_json_written: {report.get('summary', {}).get('official_json_written')}",
        "",
        "## Blocking Issues",
        "",
    ]
    issues = report.get("blocking_issues") or []
    if issues:
        for issue in issues:
            lines.append(f"- `{issue.get('issue_type')}` at `{issue.get('path', '')}`: {issue.get('message')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- `{warning.get('issue_type')}` at `{warning.get('path', '')}`: {warning.get('message')}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _check_schema_and_links(case: Any) -> dict[str, Any]:
    """Check the v0.4 top-level schema and evidence/diagnosis links."""
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(case, dict):
        return {"passed": False, "blocking_issues": [_issue("", "invalid_json_root", "Case must be a JSON object.")], "warnings": []}

    _exact_keys(case, TOP_LEVEL_KEYS, "<root>", "top_level_keys_mismatch", issues)
    _forbidden_keys(case, issues)
    hidden = case.get("hidden_reference")
    if not isinstance(hidden, dict):
        issues.append(_issue("hidden_reference", "missing_or_invalid_hidden_reference", "hidden_reference must be an object."))
        return {"passed": False, "blocking_issues": issues, "warnings": warnings}
    _exact_keys(hidden, HIDDEN_REFERENCE_KEYS, "hidden_reference", "hidden_reference_keys_mismatch", issues)
    evidence_ids = _check_evidence_units(hidden.get("reference_evidence_units"), issues)
    _check_diagnosis_units(hidden.get("reference_diagnosis_units"), evidence_ids, issues, warnings)
    return {"passed": not issues, "blocking_issues": issues, "warnings": warnings}


def _check_evidence_units(units: Any, issues: list[dict[str, Any]]) -> set[str]:
    evidence_ids: set[str] = set()
    if not isinstance(units, list):
        issues.append(_issue("hidden_reference.reference_evidence_units", "missing_or_invalid_reference_evidence_units", "reference_evidence_units must be a list."))
        return evidence_ids
    for index, unit in enumerate(units):
        base = f"hidden_reference.reference_evidence_units[{index}]"
        if not isinstance(unit, dict):
            issues.append(_issue(base, "invalid_reference_evidence_unit", "Evidence unit must be an object."))
            continue
        missing = sorted(EVIDENCE_REQUIRED_KEYS - set(unit.keys()))
        if missing:
            issues.append(_issue(base, "reference_evidence_unit_missing_keys", "Evidence unit is missing required keys.", {"missing": missing}))
        evidence_id = unit.get("evidence_id")
        if not isinstance(evidence_id, str) or not EVIDENCE_ID_PATTERN.match(evidence_id):
            issues.append(_issue(f"{base}.evidence_id", "invalid_evidence_id", "evidence_id must match E[0-9]+ or N[0-9]+."))
        elif evidence_id in evidence_ids:
            issues.append(_issue(f"{base}.evidence_id", "duplicate_evidence_id", f"Duplicate evidence_id: {evidence_id}"))
        else:
            evidence_ids.add(evidence_id)
        links = unit.get("mechanism_links")
        if links is not None and (not isinstance(links, list) or any(not isinstance(item, str) for item in links)):
            issues.append(_issue(f"{base}.mechanism_links", "invalid_mechanism_links", "mechanism_links must be an array of strings."))
        elif isinstance(links, list):
            invalid_links = sorted({item for item in links if item not in OFFICIAL_MECHANISM_SET})
            if invalid_links:
                issues.append(
                    _issue(
                        f"{base}.mechanism_links",
                        "non_official_mechanism_link",
                        "mechanism_links must use only the official mechanism vocabulary.",
                        {"invalid": invalid_links, "allowed": sorted(OFFICIAL_MECHANISM_SET)},
                    )
                )
    return evidence_ids


def _check_diagnosis_units(units: Any, evidence_ids: set[str], issues: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    if not isinstance(units, list):
        issues.append(_issue("hidden_reference.reference_diagnosis_units", "missing_or_invalid_reference_diagnosis_units", "reference_diagnosis_units must be a list."))
        return
    for index, unit in enumerate(units):
        base = f"hidden_reference.reference_diagnosis_units[{index}]"
        if not isinstance(unit, dict):
            issues.append(_issue(base, "invalid_reference_diagnosis_unit", "Diagnosis unit must be an object."))
            continue
        missing = sorted(DIAGNOSIS_REQUIRED_KEYS - set(unit.keys()))
        if missing:
            issues.append(_issue(base, "reference_diagnosis_unit_missing_keys", "Diagnosis unit is missing required keys.", {"missing": missing}))
        status = unit.get("reference_status")
        if status not in ALLOWED_REFERENCE_STATUS:
            issues.append(_issue(f"{base}.reference_status", "invalid_reference_status", "reference_status is not allowed.", {"allowed": sorted(ALLOWED_REFERENCE_STATUS)}))
        diagnosis_id = unit.get("diagnosis_id")
        if not isinstance(diagnosis_id, str) or not DIAGNOSIS_ID_PATTERN.match(diagnosis_id):
            issues.append(
                _issue(
                    f"{base}.diagnosis_id",
                    "invalid_diagnosis_id",
                    "diagnosis_id must be a purely ordinal ID in the exact form D01, D02, ... within each case.",
                    {"value": diagnosis_id},
                )
            )
        mechanism = unit.get("mechanism")
        allowed_diagnosis_mechanisms = OFFICIAL_MECHANISM_SET | SPECIAL_DIAGNOSIS_MECHANISM_SET
        if not isinstance(mechanism, str) or mechanism not in allowed_diagnosis_mechanisms:
            issues.append(
                _issue(
                    f"{base}.mechanism",
                    "non_official_diagnosis_mechanism",
                    "Diagnosis mechanism must use the official mechanism vocabulary, except for the final synthesis unit.",
                    {"allowed": sorted(allowed_diagnosis_mechanisms), "value": mechanism},
                )
            )
        supporting = unit.get("supporting_evidence_ids")
        if not isinstance(supporting, list):
            issues.append(
                _issue(
                    f"{base}.supporting_evidence_ids",
                    "invalid_supporting_evidence_ids",
                    f"supporting_evidence_ids must be a list for diagnosis_id {unit.get('diagnosis_id')}.",
                    {"diagnosis_id": unit.get("diagnosis_id")},
                )
            )
            continue
        if not supporting:
            issues.append(
                _issue(
                    f"{base}.supporting_evidence_ids",
                    "empty_supporting_evidence_ids",
                    f"supporting_evidence_ids must not be empty for diagnosis_id {unit.get('diagnosis_id')}.",
                    {"diagnosis_id": unit.get("diagnosis_id")},
                )
            )
        for evidence_id in supporting:
            if evidence_id not in evidence_ids:
                issues.append(
                    _issue(
                        f"{base}.supporting_evidence_ids",
                        "unresolved_supporting_evidence_id",
                        f"diagnosis_id {unit.get('diagnosis_id')} references unknown evidence_id {evidence_id}.",
                        {"diagnosis_id": unit.get("diagnosis_id"), "evidence_id": evidence_id},
                    )
                )


def _check_text_quality(case: Any) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for path, value in _walk_scalars(case):
        if isinstance(value, str):
            if value.strip().lower() in PLACEHOLDER_VALUES:
                issues.append(_issue(path, "placeholder_like_value", "Required field appears empty or placeholder-like."))
            if "```" in value:
                issues.append(_issue(path, "markdown_fence_in_json_string", "JSON string field contains a Markdown code fence."))
            for pattern in MOJIBAKE_PATTERNS:
                if pattern.search(value):
                    warnings.append(_issue(path, "possible_mojibake", "String contains possible mojibake or replacement characters."))
                    break
    return {"passed": not issues, "blocking_issues": issues, "warnings": warnings}


def _check_cross_candidate_identity(case: Any, locked_smiles: str | None) -> dict[str, Any]:
    """Detect direct evidence or diagnosis contamination between candidates.

    Evidence that treats a comparison or product molecule as the current
    target is blocking. The deterministic profile includes the cis/trans
    stilbene regression case.
    """
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    profile = _infer_case_identity_profile(locked_smiles)
    if not isinstance(case, dict) or not profile:
        return {
            "passed": True,
            "checked": bool(profile),
            "blocking_issues": issues,
            "warnings": warnings,
            "profile": profile,
        }

    hidden = case.get("hidden_reference")
    if not isinstance(hidden, dict):
        return {"passed": True, "checked": True, "blocking_issues": issues, "warnings": warnings, "profile": profile}

    evidence_units = hidden.get("reference_evidence_units")
    evidence_issue_ids: set[str] = set()
    if isinstance(evidence_units, list):
        for index, unit in enumerate(evidence_units):
            if not isinstance(unit, dict):
                continue
            base = f"hidden_reference.reference_evidence_units[{index}]"
            evidence_id = str(unit.get("evidence_id") or f"#{index}")
            unit_issues = _cross_candidate_evidence_issues(base, evidence_id, unit, profile)
            if unit_issues:
                evidence_issue_ids.add(evidence_id)
                issues.extend(unit_issues)

    diagnosis_units = hidden.get("reference_diagnosis_units")
    if isinstance(diagnosis_units, list):
        for index, unit in enumerate(diagnosis_units):
            if not isinstance(unit, dict):
                continue
            base = f"hidden_reference.reference_diagnosis_units[{index}]"
            issues.extend(_cross_candidate_diagnosis_issues(base, unit, profile, evidence_issue_ids))

    return {
        "passed": not issues,
        "checked": True,
        "blocking_issues": issues,
        "warnings": warnings,
        "profile": profile,
    }


def _infer_case_identity_profile(locked_smiles: str | None) -> dict[str, Any] | None:
    if not locked_smiles:
        return None
    smiles = locked_smiles.strip()
    if "/C=C\\" in smiles or "\\C=C/" in smiles:
        return {
            "target_label": "cis-stilbene",
            "target_terms": ("cis-stilbene", "cisstilbene"),
            "conflicting_label": "trans-stilbene",
            "conflicting_terms": ("trans-stilbene", "transstilbene"),
            "target_context_patterns": (
                r"\bcis-?stilbene\s+solution\b",
                r"\bcis-?stilbene\s+system\b",
                r"\bin\s+cis-?stilbene\b",
                r"\bcis-?stilbene\s+can\b",
                r"\bcis-?stilbene\s+than\b",
                r"\bthan\s+(?:the\s+)?cis-?stilbene\b",
                r"\blower\s+than\b[^.]{0,120}\bcis-?stilbene\b",
            ),
            "conflicting_direct_context_patterns": (
                r"\btrans-?stilbene\s+solution\b",
                r"\btrans-?stilbene\s+system\b",
                r"\btrans-?stilbene\s+case\b",
                r"\btrans-?stilbene-like\b",
            ),
            "bad_direct_target_patterns": (
                r"\bpublic\s+smiles\b[^.]{0,120}\btrans\b",
                r"\bpublic\b[^.]{0,80}\btrans-?stilbene\b",
                r"\btrans\b[^.]{0,80}\bencoded\b",
                r"\btrans\s+alkene\s+encoded\b",
                r"\btrans-?stilbene\s+case\b",
                r"\btrans-?stilbene-like\b",
                r"\btarget\s+molecule\b[^.]{0,80}\btrans-?stilbene\b",
            ),
        }
    if "/C=C/" in smiles or "\\C=C\\" in smiles:
        return {
            "target_label": "trans-stilbene",
            "target_terms": ("trans-stilbene", "transstilbene"),
            "conflicting_label": "cis-stilbene",
            "conflicting_terms": ("cis-stilbene", "cisstilbene"),
            "target_context_patterns": (
                r"\btrans-?stilbene\s+solution\b",
                r"\btrans-?stilbene\s+system\b",
                r"\bin\s+trans-?stilbene\b",
                r"\btrans-?stilbene\s+can\b",
                r"\btrans-?stilbene\s+than\b",
                r"\bthan\s+(?:the\s+)?trans-?stilbene\b",
                r"\blower\s+than\b[^.]{0,120}\btrans-?stilbene\b",
            ),
            "conflicting_direct_context_patterns": (
                r"\bcis-?stilbene\s+solution\b",
                r"\bcis-?stilbene\s+system\b",
                r"\bcis-?stilbene\s+case\b",
                r"\bcis-?stilbene-like\b",
            ),
            "bad_direct_target_patterns": (
                r"\bpublic\s+smiles\b[^.]{0,120}\bcis\b",
                r"\bpublic\b[^.]{0,80}\bcis-?stilbene\b",
                r"\bcis\b[^.]{0,80}\bencoded\b",
                r"\bcis\s+alkene\s+encoded\b",
                r"\bcis-?stilbene\s+case\b",
                r"\bcis-?stilbene-like\b",
                r"\btarget\s+molecule\b[^.]{0,80}\bcis-?stilbene\b",
            ),
        }
    return None


def _cross_candidate_evidence_issues(
    base: str,
    evidence_id: str,
    unit: dict[str, Any],
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    claim_text = _join_text(unit.get("claim"), unit.get("mechanistic_interpretation"), unit.get("mechanism_links"))
    quote_text = str(unit.get("paper_quote") or "")
    combined = _normalize_identity_text(f"{claim_text} {quote_text}")

    for pattern in profile["bad_direct_target_patterns"]:
        if re.search(pattern, combined, re.IGNORECASE):
            issues.append(
                _issue(
                    base,
                    "cross_candidate_direct_target_mismatch",
                    f"Evidence {evidence_id} frames {profile['conflicting_label']} as the current case molecule.",
                    {"target": profile["target_label"], "conflicting_candidate": profile["conflicting_label"]},
                )
            )
            return issues

    quote_conflict_direct = _matches_any(quote_text, profile["conflicting_direct_context_patterns"])
    quote_target_context = _matches_any(quote_text, profile["target_context_patterns"])
    quote_mentions_target = _contains_any(quote_text, profile["target_terms"])
    quote_frames_comparison_or_product = COMPARISON_OR_PRODUCT_PATTERN.search(quote_text) is not None
    claim_target_context = _matches_any(claim_text, profile["target_context_patterns"])
    if quote_conflict_direct and not quote_target_context and not (
        quote_mentions_target and quote_frames_comparison_or_product and claim_target_context
    ):
        issues.append(
            _issue(
                f"{base}.paper_quote",
                "cross_candidate_quote_about_other_candidate",
                f"Evidence {evidence_id} quotes direct {profile['conflicting_label']} context without direct {profile['target_label']} context.",
                {"target": profile["target_label"], "conflicting_candidate": profile["conflicting_label"]},
            )
        )
        return issues

    direct_mentions_conflict = _contains_any(claim_text, profile["conflicting_terms"])
    direct_mentions_target = _contains_any(claim_text, profile["target_terms"])
    if direct_mentions_conflict and not direct_mentions_target:
        issues.append(
            _issue(
                base,
                "cross_candidate_unframed_competing_candidate",
                f"Evidence {evidence_id} discusses {profile['conflicting_label']} but does not identify the current target {profile['target_label']}.",
                {"target": profile["target_label"], "conflicting_candidate": profile["conflicting_label"]},
            )
        )
    elif direct_mentions_conflict and direct_mentions_target and not COMPARISON_OR_PRODUCT_PATTERN.search(claim_text):
        issues.append(
            _issue(
                base,
                "cross_candidate_competing_candidate_not_framed",
                f"Evidence {evidence_id} mentions both target and competing candidate but does not frame the competing molecule as product, comparison, or background.",
                {"target": profile["target_label"], "conflicting_candidate": profile["conflicting_label"]},
            )
        )
    return issues


def _cross_candidate_diagnosis_issues(
    base: str,
    unit: dict[str, Any],
    profile: dict[str, Any],
    evidence_issue_ids: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    diagnosis_id = str(unit.get("diagnosis_id") or base)
    diagnosis_text = _join_text(unit.get("mechanism"), unit.get("context"), unit.get("expert_conclusion"))
    for pattern in profile["bad_direct_target_patterns"]:
        if re.search(pattern, diagnosis_text, re.IGNORECASE):
            issues.append(
                _issue(
                    base,
                    "cross_candidate_diagnosis_target_mismatch",
                    f"Diagnosis {diagnosis_id} frames {profile['conflicting_label']} as the current case molecule.",
                    {"target": profile["target_label"], "conflicting_candidate": profile["conflicting_label"]},
                )
            )
            break
    supporting = unit.get("supporting_evidence_ids")
    if isinstance(supporting, list):
        contaminated = [evidence_id for evidence_id in supporting if evidence_id in evidence_issue_ids]
        if contaminated:
            issues.append(
                _issue(
                    f"{base}.supporting_evidence_ids",
                    "cross_candidate_diagnosis_uses_contaminated_evidence",
                    f"Diagnosis {diagnosis_id} cites evidence that mainly describes another candidate molecule.",
                    {"contaminated_evidence_ids": contaminated},
                )
            )
    return issues


def _join_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts)


def _normalize_identity_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    lower = value.lower()
    return any(term.lower() in lower for term in terms)


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)


def _exact_keys(value: dict[str, Any], expected: set[str], path: str, issue_type: str, issues: list[dict[str, Any]]) -> None:
    actual = set(value.keys())
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        issues.append(_issue(path, issue_type, f"{path} keys must exactly match {sorted(expected)}.", {"missing": missing, "extra": extra}))


def _forbidden_keys(value: Any, issues: list[dict[str, Any]], path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_KEYS or key.endswith(FORBIDDEN_KEY_SUFFIXES):
                issues.append(_issue(child_path, "forbidden_key_present", f"Forbidden key is present: {key}"))
            _forbidden_keys(item, issues, child_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _forbidden_keys(item, issues, f"{path}[{index}]")


def _walk_scalars(value: Any, path: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_scalars(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_scalars(item, f"{path}[{index}]")
    else:
        yield path, value


def _tag(items: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    return [{**item, "stage": stage} for item in items]


def _issue(path: str, issue_type: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    issue = {"path": path, "issue_type": issue_type, "message": message}
    if details:
        issue["details"] = details
    return issue

"""Bounded minor repair for independently reviewed raw cases."""

from __future__ import annotations

import json
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from .local_gate import run_local_gate
from .prompting import load_prompt
from .provider import ModelClient
from .review import parse_review_decision
from .schema import validate_raw_case

FORBIDDEN_INTERNAL_ROOT_KEYS = {
    "structure_resolution_report",
    "local_gate_report",
    "review_report",
}
FORBIDDEN_INTERNAL_ROOT_SUFFIXES = ("_structure_adjudication", "_structure_review")


@dataclass(frozen=True, slots=True)
class RepairResult:
    case_id: str
    status: str
    output_dir: Path
    validation_errors: tuple[str, ...]
    local_gate_blockers: int
    changes: tuple[dict[str, Any], ...]

    @property
    def packaged_for_rereview(self) -> bool:
        return self.status == "packaged_for_rereview"


def run_minor_repair(
    *,
    original_case_path: Path,
    source_path: Path,
    structure_match_path: Path,
    review_path: Path,
    locked_structure: dict[str, Any],
    output_dir: Path,
    client: ModelClient,
    max_gate_repair_rounds: int = 1,
) -> RepairResult:
    review_text = review_path.read_text(encoding="utf-8", errors="replace")
    decision = parse_review_decision(review_text)
    if decision != "NEEDS_MINOR_FIX":
        raise ValueError(f"Minor repair requires NEEDS_MINOR_FIX; found {decision or 'no valid decision'}.")

    original = json.loads(original_case_path.read_text(encoding="utf-8-sig"))
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_minor_repair_prompt(original=original, review=review_text, source=source_text)
    (output_dir / "repair_prompt.md").write_text(prompt, encoding="utf-8")
    response = client.complete(system_prompt=_repair_system_prompt(), user_text=prompt)
    (output_dir / "repair_raw_response.txt").write_text(response.text, encoding="utf-8")
    revised, changes, errors, removed = extract_and_validate_revised(response.text, original)
    _write_json(output_dir / "initial_validation.json", {"errors": errors, "removed_internal_root_fields": removed})

    gate = _not_run_gate()
    if revised is not None and not errors:
        revised = normalize_diagnosis_ids(revised)
        gate = _run_gate(
            revised,
            source_text=source_text,
            locked_structure=locked_structure,
        )

    for round_index in range(1, max(0, max_gate_repair_rounds) + 1):
        blockers = gate.get("blocking_issues") or []
        if revised is None or errors or not blockers:
            break
        followup = build_gate_repair_prompt(
            revised=revised,
            review=review_text,
            source=source_text,
            gate=gate,
        )
        (output_dir / f"gate_repair_prompt_{round_index}.md").write_text(followup, encoding="utf-8")
        retry = client.complete(system_prompt=_repair_system_prompt(), user_text=followup)
        (output_dir / f"gate_repair_raw_response_{round_index}.txt").write_text(retry.text, encoding="utf-8")
        candidate, retry_changes, retry_errors, retry_removed = extract_and_validate_revised(retry.text, original)
        changes.extend(retry_changes)
        errors.extend(retry_errors)
        _write_json(
            output_dir / f"gate_repair_validation_{round_index}.json",
            {"errors": retry_errors, "removed_internal_root_fields": retry_removed},
        )
        if candidate is None or retry_errors:
            break
        revised = normalize_diagnosis_ids(candidate)
        gate = _run_gate(
            revised,
            source_text=source_text,
            locked_structure=locked_structure,
        )

    errors = sorted(set(errors))
    blockers = gate.get("blocking_issues") or []
    package_dir = output_dir / "rereview_input"
    packaged = revised is not None and not errors and not blockers
    if packaged:
        package_dir.mkdir(parents=True, exist_ok=True)
        _write_json(package_dir / "final_reference_alignment.json", revised)
        shutil.copy2(source_path, package_dir / "source.md")
        shutil.copy2(structure_match_path, package_dir / "structure_match.png")
    _write_json(output_dir / "local_gate_report.json", gate)
    result_record = {
        "case_id": original.get("case_id"),
        "status": "packaged_for_rereview" if packaged else "failed",
        "provider": client.provider_name,
        "model": client.model,
        "validation_errors": errors,
        "local_gate_blocker_count": len(blockers),
        "changes": changes,
        "rereview_input": str(package_dir) if packaged else None,
    }
    _write_json(output_dir / "repair_result.json", result_record)
    return RepairResult(
        case_id=str(original.get("case_id") or original_case_path.parent.name),
        status=result_record["status"],
        output_dir=output_dir,
        validation_errors=tuple(errors),
        local_gate_blockers=len(blockers),
        changes=tuple(changes),
    )


def build_minor_repair_prompt(*, original: dict[str, Any], review: str, source: str) -> str:
    return Template(load_prompt("minor_repair_v1")).substitute(
        REVIEW=review,
        SOURCE=source,
        ORIGINAL_CASE_JSON=json.dumps(original, ensure_ascii=False, indent=2),
    )


def build_gate_repair_prompt(
    *, revised: dict[str, Any], review: str, source: str, gate: dict[str, Any]
) -> str:
    return Template(load_prompt("gate_repair_v1")).substitute(
        LOCAL_GATE_REPORT=json.dumps(gate, ensure_ascii=False, indent=2),
        REVIEW=review,
        SOURCE=source,
        CURRENT_REVISED_JSON=json.dumps(revised, ensure_ascii=False, indent=2),
    )


def extract_and_validate_revised(
    response_text: str, original: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[str], list[str]]:
    try:
        parsed = _parse_json_object(response_text)
    except ValueError as exc:
        return None, [], [f"invalid_model_json:{exc}"], []
    revised = parsed.get("revised_json")
    changes = parsed.get("changes")
    if not isinstance(revised, dict):
        return None, changes if isinstance(changes, list) else [], ["missing_revised_json"], []
    revised = deepcopy(revised)
    removed = sorted(
        key
        for key in revised
        if key in FORBIDDEN_INTERNAL_ROOT_KEYS or key.endswith(FORBIDDEN_INTERNAL_ROOT_SUFFIXES)
    )
    for key in removed:
        revised.pop(key, None)
    errors: list[str] = []
    for key in ("case_id", "version", "track", "public_input"):
        if revised.get(key) != original.get(key):
            errors.append(f"protected_field_changed:{key}")
    old_source = (original.get("hidden_reference") or {}).get("source_article")
    new_source = (revised.get("hidden_reference") or {}).get("source_article")
    if new_source != old_source:
        errors.append("protected_field_changed:hidden_reference.source_article")
    errors.extend(f"schema:{issue.path}:{issue.code}" for issue in validate_raw_case(revised))
    clean_changes = [item for item in changes if isinstance(item, dict)] if isinstance(changes, list) else []
    return revised, clean_changes, sorted(set(errors)), removed


def normalize_diagnosis_ids(case: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(case)
    units = normalized["hidden_reference"]["reference_diagnosis_units"]
    for index, unit in enumerate(units, start=1):
        unit["diagnosis_id"] = f"D{index:02d}"
    return normalized


def _run_gate(
    case: dict[str, Any],
    *,
    source_text: str,
    locked_structure: dict[str, Any],
) -> dict[str, Any]:
    return run_local_gate(
        case=case,
        source_markdown=source_text,
        locked_structure=deepcopy(locked_structure),
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(parsed, dict):
        raise ValueError("response root is not an object")
    return parsed


def _repair_system_prompt() -> str:
    return (
        "You repair a reviewed AIE-DDxBench JSON case. Return only the requested JSON object. "
        "Use only the supplied case, review, and source. Never invent evidence."
    )


def _not_run_gate() -> dict[str, Any]:
    return {"gate_passed": False, "blocking_issues": [{"issue_type": "gate_not_run"}], "warnings": []}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

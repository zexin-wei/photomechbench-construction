"""JSON Schema and cross-field validation for v0.4 raw cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .vocabulary import FINAL_SYNTHESIS_MECHANISM, OFFICIAL_MECHANISM_SET


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


def load_raw_case_schema() -> dict[str, Any]:
    schema_path = files("aie_ddxbench_construction").joinpath("schemas/raw_case_v04.schema.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_raw_case(case: Any) -> list[ValidationIssue]:
    """Validate schema plus link and final-synthesis invariants."""
    issues: list[ValidationIssue] = []
    validator = Draft202012Validator(load_raw_case_schema())
    for error in sorted(validator.iter_errors(case), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        issues.append(ValidationIssue(path, "json_schema", error.message))
    if issues or not isinstance(case, dict):
        return issues

    hidden = case["hidden_reference"]
    evidence = hidden["reference_evidence_units"]
    diagnoses = hidden["reference_diagnosis_units"]
    evidence_ids = [unit["evidence_id"] for unit in evidence]
    diagnosis_ids = [unit["diagnosis_id"] for unit in diagnoses]
    issues.extend(_duplicate_issues(evidence_ids, "hidden_reference.reference_evidence_units", "duplicate_evidence_id"))
    issues.extend(_duplicate_issues(diagnosis_ids, "hidden_reference.reference_diagnosis_units", "duplicate_diagnosis_id"))

    known_evidence = set(evidence_ids)
    for index, diagnosis in enumerate(diagnoses):
        for evidence_id in diagnosis["supporting_evidence_ids"]:
            if evidence_id not in known_evidence:
                issues.append(
                    ValidationIssue(
                        f"hidden_reference.reference_diagnosis_units.{index}.supporting_evidence_ids",
                        "unknown_supporting_evidence_id",
                        f"Unknown evidence_id: {evidence_id}",
                    )
                )

    final_units = [unit for unit in diagnoses if unit["mechanism"] == FINAL_SYNTHESIS_MECHANISM]
    if len(final_units) != 1:
        issues.append(
            ValidationIssue(
                "hidden_reference.reference_diagnosis_units",
                "final_synthesis_count",
                f"Expected exactly one {FINAL_SYNTHESIS_MECHANISM} unit; found {len(final_units)}.",
            )
        )
    for index, unit in enumerate(evidence):
        invalid = sorted(set(unit["mechanism_links"]) - OFFICIAL_MECHANISM_SET)
        if invalid:
            issues.append(
                ValidationIssue(
                    f"hidden_reference.reference_evidence_units.{index}.mechanism_links",
                    "invalid_mechanism_link",
                    f"Non-official mechanism link(s): {', '.join(invalid)}",
                )
            )
    return issues


def validate_json_file(path: Path) -> list[ValidationIssue]:
    try:
        case = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [ValidationIssue("<root>", "json_read_error", str(exc))]
    return validate_raw_case(case)


def _duplicate_issues(values: Iterable[str], path: str, code: str) -> list[ValidationIssue]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return [ValidationIssue(path, code, f"Duplicate identifier: {value}") for value in sorted(duplicate)]

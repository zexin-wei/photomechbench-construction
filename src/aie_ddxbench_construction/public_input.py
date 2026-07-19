"""Read-only checks for the SMILES-only v0.4 public-input boundary.

Public input may expose only the selected SMILES and canonical generic task.
Article identity, mechanisms, observations, and results remain hidden. This
module is deterministic and does not call models, invoke RDKit, or write JSON.
"""

from __future__ import annotations

import re
from typing import Any


CANONICAL_SMILES_ONLY_TASK = (
    "Starting from the SMILES structure only, autonomously investigate possible AIE/photophysical mechanisms. "
    "Report generated evidence, supported mechanisms, weakened or rejected mechanisms, underdetermined mechanisms, "
    "necessary wet-lab follow-ups, and a final evidence-grounded mechanistic diagnosis."
)

PUBLIC_INPUT_ALLOWED_KEYS = {"molecule", "task"}
PUBLIC_MOLECULE_ALLOWED_KEYS = {"structure"}
PUBLIC_STRUCTURE_ALLOWED_KEYS = {"format", "value"}
FORBIDDEN_PUBLIC_STRUCTURE_KEYS = {
    "case_molecule_id",
    "material_type",
    "structure_files",
    "image_2d",
    "image_path",
    "neutral_structure_description",
    "name",
    "molecule_name",
    "abbreviation",
    "synonym",
    "iupac_name",
    "cas",
    "cas_number",
    "pubchem_cid",
    "pubchem_query",
    "selected_source",
    "resolved_from",
    "resolution_status",
    "source_type",
    "structure_resolution_report",
    "identity_hints",
}
CASE_SPECIFIC_LEAKAGE_PATTERNS = (
    re.compile(r"\bdoi\b", re.IGNORECASE),
    re.compile(r"\bpubchem\b", re.IGNORECASE),
    re.compile(r"\bCAS\b", re.IGNORECASE),
    re.compile(r"\bHPQ\b", re.IGNORECASE),
    re.compile(r"\bESIPT\b", re.IGNORECASE),
    re.compile(r"\bTICT\b", re.IGNORECASE),
    re.compile(r"\bRIR\b", re.IGNORECASE),
    re.compile(r"\bRACI\b", re.IGNORECASE),
    re.compile(r"\bICT\b", re.IGNORECASE),
    re.compile(r"\bemission\b", re.IGNORECASE),
    re.compile(r"\bfluorescence\b", re.IGNORECASE),
    re.compile(r"\bquantum yield\b", re.IGNORECASE),
    re.compile(r"\bsolution\b", re.IGNORECASE),
    re.compile(r"\bsolid\b", re.IGNORECASE),
    re.compile(r"\bcrystal(?:line)?\b", re.IGNORECASE),
    re.compile(r"\bconical intersection\b", re.IGNORECASE),
)


def check_smiles_only_public_input(case: Any, locked_smiles: str | None) -> dict[str, Any]:
    """Validate the public-input shape and exact selected-SMILES lock.

    Schema, format, task, and SMILES mismatches are blocking. Possible
    case-specific leakage terms are reported as reviewer warnings.
    """
    blocking_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(case, dict):
        return _report(False, blocking_issues=[_issue("", "invalid_json_root", "Case must be a JSON object.")])

    public_input = case.get("public_input")
    if not isinstance(public_input, dict):
        blocking_issues.append(_issue("public_input", "missing_or_invalid_public_input", "public_input must be an object."))
        return _report(False, blocking_issues=blocking_issues, warnings=warnings)

    _check_exact_keys(public_input, PUBLIC_INPUT_ALLOWED_KEYS, "public_input", blocking_issues)
    task = public_input.get("task")
    if task != CANONICAL_SMILES_ONLY_TASK:
        blocking_issues.append(
            _issue(
                "public_input.task",
                "invalid_smiles_only_task",
                "public_input.task must match the canonical SMILES-only task wording exactly.",
            )
        )
    molecule = public_input.get("molecule")
    if not isinstance(molecule, dict):
        blocking_issues.append(_issue("public_input.molecule", "missing_or_invalid_molecule", "public_input.molecule must be an object."))
        return _report(False, blocking_issues=blocking_issues, warnings=warnings)
    _check_exact_keys(molecule, PUBLIC_MOLECULE_ALLOWED_KEYS, "public_input.molecule", blocking_issues)

    structure = molecule.get("structure")
    if not isinstance(structure, dict):
        blocking_issues.append(
            _issue(
                "public_input.molecule.structure",
                "invalid_public_structure",
                "public_input.molecule.structure must be a SMILES object.",
            )
        )
        return _report(False, blocking_issues=blocking_issues, warnings=warnings)
    _check_exact_keys(structure, PUBLIC_STRUCTURE_ALLOWED_KEYS, "public_input.molecule.structure", blocking_issues)
    for key in structure:
        if key in FORBIDDEN_PUBLIC_STRUCTURE_KEYS:
            blocking_issues.append(
                _issue(
                    f"public_input.molecule.structure.{key}",
                    "forbidden_public_structure_field",
                    f"Forbidden public structure field is present: {key}",
                )
            )
    if structure.get("format") != "smiles":
        blocking_issues.append(
            _issue(
                "public_input.molecule.structure.format",
                "invalid_public_structure_format",
                "public_input.molecule.structure.format must be exactly 'smiles'.",
            )
        )
    value = structure.get("value")
    if not isinstance(value, str) or not value.strip():
        blocking_issues.append(
            _issue(
                "public_input.molecule.structure.value",
                "missing_public_structure_smiles",
                "public_input.molecule.structure.value must be a non-empty SMILES string.",
            )
        )
    elif locked_smiles is not None and value.strip() != locked_smiles:
        blocking_issues.append(
            _issue(
                "public_input.molecule.structure.value",
                "public_smiles_mismatch",
                "public_input SMILES must exactly match locked_smiles from locked_structure.json.",
                {"public_smiles": value.strip(), "locked_smiles": locked_smiles},
            )
        )

    public_text = str(public_input)
    for pattern in CASE_SPECIFIC_LEAKAGE_PATTERNS:
        match = pattern.search(public_text)
        if match:
            warnings.append(
                _issue(
                    "public_input",
                    "public_input_possible_case_specific_leakage",
                    f"public_input contains possible case-specific leakage term: {match.group(0)}",
                )
            )
    return _report(not blocking_issues, blocking_issues=blocking_issues, warnings=warnings)


def _check_exact_keys(value: dict[str, Any], allowed: set[str], path: str, issues: list[dict[str, Any]]) -> None:
    actual = set(value.keys())
    extra = sorted(actual - allowed)
    missing = sorted(allowed - actual)
    if extra or missing:
        issues.append(
            _issue(
                path,
                "public_input_keys_mismatch",
                f"{path} keys must exactly match {sorted(allowed)}.",
                {"extra": extra, "missing": missing},
            )
        )


def _issue(path: str, issue_type: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {"path": path, "issue_type": issue_type, "message": message}
    if details:
        item["details"] = details
    return item


def _report(passed: bool, *, blocking_issues: list[dict[str, Any]], warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    warnings = warnings or []
    return {
        "check_name": "smiles_only_public_input_gate",
        "checked": True,
        "passed": passed,
        "canonical_task": CANONICAL_SMILES_ONLY_TASK,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
    }

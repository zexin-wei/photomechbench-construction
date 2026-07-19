"""Read-only validation for the canonical locked-structure artifact."""

from __future__ import annotations

from typing import Any

from .chemistry import validate_smiles_with_rdkit


def check_locked_structure(
    locked_structure: Any,
    *,
    allow_provisional_structure: bool = False,
) -> dict[str, Any]:
    """Validate the canonical ``locked_structure.json`` contract."""
    blocking_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(locked_structure, dict):
        return {
            "checked": True,
            "passed": False,
            "locked_smiles": None,
            "final_structure_status": None,
            "rdkit_validation": None,
            "blocking_issues": [
                {
                    "issue_type": "invalid_locked_structure",
                    "path": "<locked_structure>",
                    "message": "locked_structure.json must contain a JSON object.",
                }
            ],
            "warnings": [],
        }

    smiles_value = locked_structure.get("locked_smiles")
    locked_smiles = smiles_value.strip() if isinstance(smiles_value, str) and smiles_value.strip() else None
    status_value = locked_structure.get("final_structure_status")
    final_status = status_value.strip() if isinstance(status_value, str) and status_value.strip() else None

    if not locked_smiles:
        blocking_issues.append(
            {
                "issue_type": "missing_locked_smiles",
                "path": "locked_smiles",
                "message": "locked_structure.json must contain a non-empty locked_smiles value.",
            }
        )
    if not final_status:
        blocking_issues.append(
            {
                "issue_type": "missing_final_structure_status",
                "path": "final_structure_status",
                "message": "locked_structure.json must contain final_structure_status.",
            }
        )
    elif final_status != "validated":
        issue = {
            "issue_type": "structure_status_not_validated",
            "path": "final_structure_status",
            "message": "final_structure_status must be validated unless provisional structure is explicitly allowed.",
            "status": final_status,
        }
        if allow_provisional_structure and final_status == "provisional":
            warnings.append(issue)
        else:
            blocking_issues.append(issue)

    unresolved = locked_structure.get("unresolved_structure_concerns")
    if isinstance(unresolved, list) and unresolved:
        blocking_issues.append(
            {
                "issue_type": "unresolved_structure_concerns",
                "path": "unresolved_structure_concerns",
                "message": "locked_structure.json has unresolved structure concerns.",
                "count": len(unresolved),
            }
        )

    rdkit_validation = validate_smiles_with_rdkit(locked_smiles) if locked_smiles else None
    if rdkit_validation:
        for issue in rdkit_validation.get("blocking_issues", []):
            if isinstance(issue, dict):
                blocking_issues.append(
                    {
                        "issue_type": issue.get("issue_type", "rdkit_validation_blocking_issue"),
                        "path": "locked_smiles",
                        "message": "RDKit validation failed for locked_smiles.",
                        "rdkit_issue": issue,
                    }
                )
        for warning in rdkit_validation.get("warnings", []):
            if isinstance(warning, dict):
                warnings.append(
                    {
                        "issue_type": warning.get("issue_type", "rdkit_validation_warning"),
                        "path": "locked_smiles",
                        "message": "RDKit could not fully validate locked_smiles.",
                        "rdkit_warning": warning,
                    }
                )

    return {
        "checked": True,
        "passed": not blocking_issues,
        "locked_smiles": locked_smiles,
        "final_structure_status": final_status,
        "rdkit_validation": rdkit_validation,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
    }

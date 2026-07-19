"""Deterministic RDKit validation helpers for v0.4 molecular structures.

The module validates parsing, sanitization, canonical SMILES, formula,
molecular weight, stereochemistry, expected-formula agreement, and optional
comparison-SMILES equivalence. It never calls a language model or writes case
JSON.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


RDKIT_PYTHON_ENV = "AIE_DDX_RDKIT_PYTHON"
RDKIT_CONDA_ENV = "AIE_DDX_RDKIT_CONDA_ENV"


def external_runtime_environment(runtime_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Expose this source tree to a configured external RDKit interpreter."""
    child_env = dict(runtime_env if runtime_env is not None else os.environ)
    source_root = str(Path(__file__).resolve().parents[1])
    current = str(child_env.get("PYTHONPATH") or "").strip()
    entries = [entry for entry in current.split(os.pathsep) if entry]
    if source_root not in entries:
        child_env["PYTHONPATH"] = os.pathsep.join([source_root, *entries])
    return child_env


def validate_smiles_with_rdkit(
    smiles: Any,
    *,
    expected_formula: Any = None,
    comparison_smiles: Any = None,
    supplemental_report: Any = None,
    allow_runtime_fallback: bool = True,
    runtime_env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate a SMILES and return a JSON-safe RDKit report.

    Runtime order is the current interpreter, configured external Python,
    configured conda environment, then a trusted supplemental report. An
    unavailable runtime is reported explicitly and is never presented as a
    successful live validation.
    """

    input_smiles = str(smiles or "").strip()
    expected = _clean_optional_string(expected_formula)
    comparison = _clean_optional_string(comparison_smiles)
    env = runtime_env if runtime_env is not None else os.environ

    current_report = _validate_with_current_rdkit(
        input_smiles,
        expected_formula=expected,
        comparison_smiles=comparison,
    )
    if current_report.get("rdkit_available"):
        # Live RDKit results take precedence, including parse/sanitize failures.
        return current_report

    warnings = list(current_report.get("warnings") or [])

    if allow_runtime_fallback:
        fallback_report, fallback_warnings = _try_runtime_fallbacks(
            input_smiles,
            expected_formula=expected,
            comparison_smiles=comparison,
            env=env,
        )
        warnings.extend(fallback_warnings)
        if fallback_report and fallback_report.get("rdkit_available"):
            return fallback_report

    supplemental = _load_supplemental_report(supplemental_report)
    if supplemental is not None:
        trusted, supplemental_result, supplemental_warnings = _trusted_supplemental_report(
            supplemental,
            input_smiles=input_smiles,
            expected_formula=expected,
            comparison_smiles=comparison,
        )
        if trusted:
            return supplemental_result
        warnings.extend(supplemental_warnings)

    report = _base_report(input_smiles, expected, comparison)
    report["warnings"] = warnings or [
        {
            "issue_type": "rdkit_unavailable",
            "message": "RDKit was unavailable in current Python and no fallback runtime was configured.",
        }
    ]
    return report


def _validate_with_current_rdkit(
    smiles: str,
    *,
    expected_formula: str | None = None,
    comparison_smiles: str | None = None,
) -> dict[str, Any]:
    report = _base_report(smiles, expected_formula, comparison_smiles)
    report["runtime_source"] = "current_python"
    report["runtime_label"] = sys.executable or "current_python"

    try:
        from rdkit import Chem  # type: ignore
        from rdkit.Chem import Descriptors, rdMolDescriptors  # type: ignore
    except Exception as exc:
        report["warnings"].append(
            {
                "issue_type": "rdkit_unavailable",
                "message": f"{type(exc).__name__}: {exc}",
                "runtime_source": "current_python",
                "runtime_label": report["runtime_label"],
            }
        )
        return report

    report["rdkit_available"] = True
    mol, parse_error = _parse_and_sanitize(Chem, smiles)
    if mol is None:
        report["blocking_issues"].append(
            {
                "issue_type": "rdkit_parse_or_sanitize_failed",
                "message": parse_error or "RDKit could not parse/sanitize the SMILES.",
            }
        )
        return report

    report["parse_success"] = True
    report["sanitize_success"] = True
    report["canonical_smiles"] = Chem.MolToSmiles(mol, isomericSmiles=True)
    report["formula"] = rdMolDescriptors.CalcMolFormula(mol)
    report["molecular_weight"] = round(float(Descriptors.MolWt(mol)), 4)
    report["chiral_centers"] = [
        {"atom_index": int(atom_index), "label": str(label)}
        for atom_index, label in Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    ]
    report["stereo_bonds"] = _stereo_bonds(mol)
    _apply_expected_formula_policy(report, expected_formula)
    _apply_comparison_policy(report, Chem, comparison_smiles)
    return report


def _try_runtime_fallbacks(
    smiles: str,
    *,
    expected_formula: str | None,
    comparison_smiles: str | None,
    env: Mapping[str, str],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Try configured external RDKit runtimes after current-Python failure."""
    warnings: list[dict[str, Any]] = []
    python_path = _clean_optional_string(env.get(RDKIT_PYTHON_ENV))
    if python_path:
        command = _external_python_command(python_path, smiles, expected_formula, comparison_smiles)
        report, warning = _run_external_rdkit_validation(
            command,
            runtime_source="external_python",
            runtime_label=python_path,
            runtime_env=env,
        )
        if report:
            return report, warnings
        warnings.append(warning)

    conda_env = _clean_optional_string(env.get(RDKIT_CONDA_ENV))
    if conda_env:
        command = _conda_command(conda_env, smiles, expected_formula, comparison_smiles)
        report, warning = _run_external_rdkit_validation(
            command,
            runtime_source="conda_env",
            runtime_label=conda_env,
            runtime_env=env,
        )
        if report:
            return report, warnings
        warnings.append(warning)

    return None, warnings


def _external_python_command(
    python_path: str,
    smiles: str,
    expected_formula: str | None,
    comparison_smiles: str | None,
) -> list[str]:
    command = [
        python_path,
        "-m",
        "aie_ddxbench_construction.chemistry_cli",
        "--smiles",
        smiles,
    ]
    if expected_formula:
        command.extend(["--expected-formula", expected_formula])
    if comparison_smiles:
        command.extend(["--comparison-smiles", comparison_smiles])
    return command


def _conda_command(
    conda_env: str,
    smiles: str,
    expected_formula: str | None,
    comparison_smiles: str | None,
) -> list[str]:
    return [
        "conda",
        "run",
        "-n",
        conda_env,
        *_external_python_command("python", smiles, expected_formula, comparison_smiles),
    ]


def _run_external_rdkit_validation(
    command: Sequence[str],
    *,
    runtime_source: str,
    runtime_label: str,
    runtime_env: Mapping[str, str] | None = None,
    timeout_seconds: int = 90,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Run the validation CLI in an external runtime.

    A report is returned only for valid JSON with ``rdkit_available=true``.
    Command errors, timeouts, invalid JSON, and unavailable RDKit become
    explicit warnings rather than silent success.
    """
    safe_command = [str(part) for part in command]
    try:
        completed = subprocess.run(
            safe_command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=external_runtime_environment(runtime_env),
        )
    except Exception as exc:
        return None, _external_runtime_warning(
            runtime_source=runtime_source,
            runtime_label=runtime_label,
            command=safe_command,
            message=f"{type(exc).__name__}: {exc}",
        )

    stdout = (completed.stdout or "").strip()
    if completed.returncode != 0:
        message = (completed.stderr or stdout or f"returncode={completed.returncode}").strip()
        return None, _external_runtime_warning(
            runtime_source=runtime_source,
            runtime_label=runtime_label,
            command=safe_command,
            message=message,
        )

    try:
        parsed = json.loads(stdout)
    except Exception as exc:
        return None, _external_runtime_warning(
            runtime_source=runtime_source,
            runtime_label=runtime_label,
            command=safe_command,
            message=f"invalid_json_stdout: {type(exc).__name__}: {exc}",
        )

    if not isinstance(parsed, dict):
        return None, _external_runtime_warning(
            runtime_source=runtime_source,
            runtime_label=runtime_label,
            command=safe_command,
            message="external RDKit validation did not return a JSON object",
        )

    child_runtime_source = parsed.get("runtime_source")
    child_runtime_label = parsed.get("runtime_label")
    parsed["runtime_source"] = runtime_source
    parsed["runtime_label"] = runtime_label
    parsed["runtime_command"] = _safe_runtime_command(safe_command)
    parsed["child_runtime_source"] = child_runtime_source
    parsed["child_runtime_label"] = child_runtime_label
    parsed.setdefault("rdkit_runtime_label", child_runtime_label or runtime_label)
    if not parsed.get("rdkit_available"):
        warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
        message = "external RDKit runtime reported unavailable"
        if warnings and isinstance(warnings[0], dict):
            message = str(warnings[0].get("message") or message)
        return None, _external_runtime_warning(
            runtime_source=runtime_source,
            runtime_label=runtime_label,
            command=safe_command,
            message=message,
        )
    return parsed, {}


def _external_runtime_warning(
    *,
    runtime_source: str,
    runtime_label: str,
    command: Sequence[str],
    message: str,
) -> dict[str, Any]:
    return {
        "issue_type": "rdkit_runtime_fallback_failed",
        "runtime_source": runtime_source,
        "runtime_label": runtime_label,
        "runtime_command": _safe_runtime_command(command),
        "message": message,
    }


def _safe_runtime_command(command: Sequence[str]) -> list[str]:
    return [str(part) for part in command]


def _load_supplemental_report(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        path = Path(str(value)).expanduser()
        if not path.is_file():
            return {
                "_supplemental_load_error": f"supplemental report path not found: {path}",
            }
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "_supplemental_load_error": f"{type(exc).__name__}: {exc}",
        }
    return data if isinstance(data, dict) else {"_supplemental_load_error": "supplemental report is not a JSON object"}


def _trusted_supplemental_report(
    report: dict[str, Any],
    *,
    input_smiles: str,
    expected_formula: str | None,
    comparison_smiles: str | None,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    """Validate and normalize an offline supplemental RDKit report.

    Reports with missing provenance, input mismatches, failed parsing or
    sanitization, or formula disagreement are rejected. Supplemental evidence
    is considered only when every live RDKit runtime is unavailable.
    """
    warnings: list[dict[str, Any]] = []
    load_error = report.get("_supplemental_load_error")
    if load_error:
        warnings.append({"issue_type": "rdkit_supplemental_report_rejected", "message": str(load_error)})
        return False, {}, warnings

    required = {
        "input_smiles",
        "canonical_smiles",
        "formula",
        "parse_success",
        "sanitize_success",
        "expected_formula",
        "formula_matches_expected",
        "rdkit_runtime_label",
    }
    missing = sorted(key for key in required if key not in report)
    if not (report.get("generated_at") or report.get("provenance")):
        missing.append("generated_at_or_provenance")
    if missing:
        warnings.append(
            {
                "issue_type": "rdkit_supplemental_report_rejected",
                "message": "supplemental report is missing required provenance or validation fields",
                "missing_fields": missing,
            }
        )
        return False, {}, warnings

    if str(report.get("input_smiles") or "").strip() != input_smiles:
        warnings.append(
            {
                "issue_type": "rdkit_supplemental_report_rejected",
                "message": "supplemental report input_smiles does not match current SMILES exactly",
                "report_input_smiles": report.get("input_smiles"),
                "current_input_smiles": input_smiles,
            }
        )
        return False, {}, warnings

    if expected_formula:
        report_expected = _clean_optional_string(report.get("expected_formula"))
        if _normalize_formula(report_expected) != _normalize_formula(expected_formula):
            warnings.append(
                {
                    "issue_type": "rdkit_supplemental_report_rejected",
                    "message": "supplemental report expected_formula does not match current expected_formula",
                    "report_expected_formula": report_expected,
                    "current_expected_formula": expected_formula,
                }
            )
            return False, {}, warnings

    if not report.get("parse_success") or not report.get("sanitize_success"):
        warnings.append(
            {
                "issue_type": "rdkit_supplemental_report_rejected",
                "message": "supplemental report parse/sanitize did not pass",
            }
        )
        return False, {}, warnings

    if expected_formula and report.get("formula_matches_expected") is not True:
        warnings.append(
            {
                "issue_type": "rdkit_supplemental_report_rejected",
                "message": "supplemental report formula_matches_expected is not true",
            }
        )
        return False, {}, warnings

    result = _base_report(input_smiles, expected_formula, comparison_smiles)
    result.update(
        {
            "rdkit_available": True,
            "parse_success": True,
            "sanitize_success": True,
            "canonical_smiles": report.get("canonical_smiles"),
            "formula": report.get("formula"),
            "molecular_weight": report.get("molecular_weight"),
            "chiral_centers": report.get("chiral_centers") if isinstance(report.get("chiral_centers"), list) else [],
            "stereo_bonds": report.get("stereo_bonds") if isinstance(report.get("stereo_bonds"), list) else [],
            "formula_matches_expected": report.get("formula_matches_expected"),
            "comparison_canonical_smiles": report.get("comparison_canonical_smiles"),
            "comparison_equivalent": report.get("comparison_equivalent"),
            "runtime_source": "supplemental_report",
            "runtime_label": report.get("rdkit_runtime_label"),
            "rdkit_runtime_label": report.get("rdkit_runtime_label"),
            "supplemental_report_trusted": True,
            "generated_at": report.get("generated_at"),
            "provenance": report.get("provenance"),
        }
    )
    if expected_formula:
        result["formula_matches_expected"] = _normalize_formula(result.get("formula")) == _normalize_formula(expected_formula)
        if not result["formula_matches_expected"]:
            warnings.append(
                {
                    "issue_type": "rdkit_supplemental_report_rejected",
                    "message": "supplemental report formula does not match current expected_formula",
                    "report_formula": result.get("formula"),
                    "current_expected_formula": expected_formula,
                }
            )
            return False, {}, warnings
    return True, result, []


def _base_report(input_smiles: str, expected: str | None, comparison: str | None) -> dict[str, Any]:
    return {
        "rdkit_available": False,
        "parse_success": False,
        "sanitize_success": False,
        "canonical_smiles": None,
        "formula": None,
        "molecular_weight": None,
        "chiral_centers": [],
        "stereo_bonds": [],
        "expected_formula": expected,
        "formula_matches_expected": None,
        "comparison_smiles": comparison,
        "comparison_equivalent": None,
        "comparison_canonical_smiles": None,
        "blocking_issues": [],
        "warnings": [],
        "input_smiles": input_smiles,
        "runtime_source": None,
        "runtime_label": None,
    }


def _parse_and_sanitize(Chem: Any, smiles: str) -> tuple[Any | None, str | None]:
    if not smiles:
        return None, "empty_smiles"
    try:
        mol = Chem.MolFromSmiles(smiles, sanitize=False)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if mol is None:
        return None, "rdkit_parse_failed"
    try:
        Chem.SanitizeMol(mol)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return mol, None


def _apply_expected_formula_policy(report: dict[str, Any], expected: str | None) -> None:
    if not expected:
        return
    report["formula_matches_expected"] = _normalize_formula(report["formula"]) == _normalize_formula(expected)
    if not report["formula_matches_expected"]:
        report["blocking_issues"].append(
            {
                "issue_type": "formula_mismatch",
                "expected_formula": expected,
                "actual_formula": report["formula"],
            }
        )


def _apply_comparison_policy(report: dict[str, Any], Chem: Any, comparison: str | None) -> None:
    if not comparison:
        return
    comparison_mol, comparison_error = _parse_and_sanitize(Chem, comparison)
    if comparison_mol is None:
        report["comparison_equivalent"] = False
        report["blocking_issues"].append(
            {
                "issue_type": "comparison_smiles_parse_or_sanitize_failed",
                "comparison_smiles": comparison,
                "message": comparison_error or "RDKit could not parse/sanitize comparison_smiles.",
            }
        )
        return
    comparison_canonical = Chem.MolToSmiles(comparison_mol, isomericSmiles=True)
    report["comparison_canonical_smiles"] = comparison_canonical
    report["comparison_equivalent"] = report["canonical_smiles"] == comparison_canonical
    if not report["comparison_equivalent"]:
        report["blocking_issues"].append(
            {
                "issue_type": "comparison_smiles_not_equivalent",
                "canonical_smiles": report["canonical_smiles"],
                "comparison_canonical_smiles": comparison_canonical,
            }
        )


def _stereo_bonds(mol: Any) -> list[dict[str, Any]]:
    bonds: list[dict[str, Any]] = []
    for bond in mol.GetBonds():
        stereo = str(bond.GetStereo())
        if stereo == "STEREONONE":
            continue
        bonds.append(
            {
                "bond_index": int(bond.GetIdx()),
                "begin_atom_index": int(bond.GetBeginAtomIdx()),
                "end_atom_index": int(bond.GetEndAtomIdx()),
                "stereo": stereo,
            }
        )
    return bonds


def _clean_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_formula(value: Any) -> str:
    return "".join(str(value or "").split())

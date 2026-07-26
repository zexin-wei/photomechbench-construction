"""Stage 4 construction of source-grounded v0.4 hidden references."""

from __future__ import annotations

import json
import shutil
import hashlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .json_io import parse_json_object
from .local_gate import render_local_gate_markdown, run_local_gate
from .provider import ModelClient
from .prompting import load_prompt
from .public_input import CANONICAL_SMILES_ONLY_TASK
from .repair import normalize_diagnosis_ids
from .schema import validate_raw_case
from .vocabulary import FINAL_SYNTHESIS_MECHANISM, OFFICIAL_MECHANISMS, RAW_CASE_SCHEMA_VERSION, RAW_CASE_TRACK

REFERENCE_SYSTEM_PROMPT = (
    "You construct a source-grounded PhotoMechBench v0.4 reference case. "
    "Use only the supplied source and locked target. Return exactly one JSON object."
)
REFERENCE_PROMPT_VERSION = "reference_construction_v1"
REFERENCE_GATE_REPAIR_PROMPT_VERSION = "reference_gate_repair_v1"


@dataclass(frozen=True, slots=True)
class ReferenceTask:
    case_id: str
    source_md: Path
    locked_structure: Path
    structure_match: Path
    source_article: dict[str, Any]
    target_context: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ReferenceResult:
    case_id: str
    status: str
    output_dir: Path
    gate_passed: bool
    error: str | None = None


def run_reference_construction(
    task: ReferenceTask,
    *,
    output_dir: Path,
    client: ModelClient,
    allow_one_gate_repair: bool = True,
    resume: bool = False,
) -> ReferenceResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = task.source_md.read_text(encoding="utf-8", errors="replace")
    lock = json.loads(task.locked_structure.read_text(encoding="utf-8"))
    locked_smiles = _validated_lock(task, lock)
    if resume and _valid_delivery(task, output_dir=output_dir, source=source, lock=lock, locked_smiles=locked_smiles):
        return ReferenceResult(task.case_id, "skipped_valid", output_dir, True)
    prompt = build_reference_prompt(task, source=source, locked_smiles=locked_smiles)
    try:
        case = _model_case(client, prompt=prompt, output_dir=output_dir / "01_draft", prompt_version=REFERENCE_PROMPT_VERSION)
        case = normalize_diagnosis_ids(case)
        errors = _immutable_and_schema_errors(case, task=task, locked_smiles=locked_smiles)
        if errors:
            gate = _synthetic_gate(errors)
        else:
            gate = run_local_gate(case=case, source_markdown=source, locked_structure=lock)
        _write_gate(output_dir / "02_local_gate", gate)

        if not gate.get("gate_passed") and allow_one_gate_repair:
            repaired = _model_case(
                client,
                prompt=build_reference_gate_repair_prompt(case=case, gate=gate, source=source, lock=lock),
                output_dir=output_dir / "03_gate_repair",
                prompt_version=REFERENCE_GATE_REPAIR_PROMPT_VERSION,
            )
            repaired = normalize_diagnosis_ids(repaired)
            protected_errors = _repair_protection_errors(original=case, repaired=repaired, task=task, locked_smiles=locked_smiles)
            if protected_errors:
                gate = _synthetic_gate(protected_errors)
            else:
                case = repaired
                gate = run_local_gate(case=case, source_markdown=source, locked_structure=lock)
            _write_gate(output_dir / "04_repaired_local_gate", gate)

        _write_json(output_dir / "reference_construction_summary.json", {"case_id": task.case_id, "gate_passed": bool(gate.get("gate_passed")), "gate": gate, "completed_at": datetime.now(timezone.utc).isoformat()})
        if not gate.get("gate_passed"):
            return ReferenceResult(task.case_id, "failed_gate", output_dir, False, "deterministic local gate did not pass")

        delivery = output_dir / "delivery"
        delivery.mkdir(parents=True, exist_ok=True)
        _write_json(delivery / "final_reference_alignment.json", case)
        shutil.copy2(task.source_md, delivery / "source.md")
        shutil.copy2(task.structure_match, delivery / "structure_match.png")
        shutil.copy2(task.locked_structure, delivery / "locked_structure.json")
        return ReferenceResult(task.case_id, "completed", output_dir, True)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        _write_json(output_dir / "reference_construction_summary.json", {"case_id": task.case_id, "gate_passed": False, "error": error, "failed_at": datetime.now(timezone.utc).isoformat()})
        return ReferenceResult(task.case_id, "failed", output_dir, False, error)


def build_reference_prompt(task: ReferenceTask, *, source: str, locked_smiles: str) -> str:
    context = task.target_context or {}
    policy = load_prompt(REFERENCE_PROMPT_VERSION)
    return f"""{policy}

Required identity:
- case_id: {task.case_id}
- version: {RAW_CASE_SCHEMA_VERSION}
- track: {RAW_CASE_TRACK}
- locked SMILES: {locked_smiles}
- source_article: {json.dumps(task.source_article, ensure_ascii=False)}

Targeting context for hidden-reference evidence selection only:
{json.dumps(context, ensure_ascii=False, indent=2)}

public_input must be exactly:
{json.dumps(_public_input(locked_smiles), ensure_ascii=False, indent=2)}

Official mechanism vocabulary:
{json.dumps(list(OFFICIAL_MECHANISMS), ensure_ascii=False, indent=2)}

Reserved final synthesis label: {FINAL_SYNTHESIS_MECHANISM}

SOURCE_PAGE_AWARE_MARKDOWN:
```markdown
{source}
```
"""


def build_reference_gate_repair_prompt(*, case: dict[str, Any], gate: dict[str, Any], source: str, lock: dict[str, Any]) -> str:
    policy = load_prompt(REFERENCE_GATE_REPAIR_PROMPT_VERSION)
    return f"""{policy}

LOCAL_GATE_REPORT:
{json.dumps(gate, ensure_ascii=False, indent=2)}

LOCKED_STRUCTURE:
{json.dumps(lock, ensure_ascii=False, indent=2)}

CURRENT_CASE:
{json.dumps(case, ensure_ascii=False, indent=2)}

SOURCE_PAGE_AWARE_MARKDOWN:
```markdown
{source}
```
"""


def _model_case(client: ModelClient, *, prompt: str, output_dir: Path, prompt_version: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "request.json", {"prompt_version": prompt_version, "provider": client.provider_name, "model": client.model, "system_prompt": REFERENCE_SYSTEM_PROMPT, "user_text": prompt})
    (output_dir / "request.md").write_text(prompt, encoding="utf-8")
    response = client.complete(system_prompt=REFERENCE_SYSTEM_PROMPT, user_text=prompt)
    (output_dir / "raw_response.txt").write_text(response.text, encoding="utf-8")
    case = parse_json_object(response.text)
    _write_json(output_dir / "result.json", case)
    return case


def _validated_lock(task: ReferenceTask, lock: dict[str, Any]) -> str:
    if lock.get("candidate_id") not in {None, task.source_article.get("candidate_id")}:
        raise ValueError("locked_structure candidate_id conflicts with source_article candidate_id")
    if lock.get("final_structure_status") != "validated":
        raise ValueError("locked_structure is not validated")
    smiles = str(lock.get("locked_smiles") or "").strip()
    if not smiles:
        raise ValueError("locked_structure has no final SMILES")
    return smiles


def _immutable_and_schema_errors(case: dict[str, Any], *, task: ReferenceTask, locked_smiles: str) -> list[str]:
    errors = [f"schema:{issue.path}:{issue.code}" for issue in validate_raw_case(case)]
    if case.get("case_id") != task.case_id:
        errors.append("case_id_changed")
    if case.get("version") != RAW_CASE_SCHEMA_VERSION or case.get("track") != RAW_CASE_TRACK:
        errors.append("version_or_track_changed")
    if case.get("public_input") != _public_input(locked_smiles):
        errors.append("public_input_or_locked_smiles_changed")
    source_article = (case.get("hidden_reference") or {}).get("source_article")
    if source_article != task.source_article:
        errors.append("source_article_changed")
    return errors


def _repair_protection_errors(*, original: dict[str, Any], repaired: dict[str, Any], task: ReferenceTask, locked_smiles: str) -> list[str]:
    errors = _immutable_and_schema_errors(repaired, task=task, locked_smiles=locked_smiles)
    for key in ("case_id", "version", "track", "public_input"):
        if repaired.get(key) != original.get(key):
            errors.append(f"protected_field_changed:{key}")
    old_source = (original.get("hidden_reference") or {}).get("source_article")
    new_source = (repaired.get("hidden_reference") or {}).get("source_article")
    if old_source != new_source:
        errors.append("protected_field_changed:hidden_reference.source_article")
    return sorted(set(errors))


def _public_input(smiles: str) -> dict[str, Any]:
    return {"molecule": {"structure": {"format": "smiles", "value": smiles}}, "task": CANONICAL_SMILES_ONLY_TASK}


def _valid_delivery(
    task: ReferenceTask,
    *,
    output_dir: Path,
    source: str,
    lock: dict[str, Any],
    locked_smiles: str,
) -> bool:
    delivery = output_dir / "delivery"
    json_path = delivery / "final_reference_alignment.json"
    source_path = delivery / "source.md"
    match_path = delivery / "structure_match.png"
    if not all(path.is_file() for path in (json_path, source_path, match_path)):
        return False
    try:
        case = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    if _immutable_and_schema_errors(case, task=task, locked_smiles=locked_smiles):
        return False
    if _sha256(source_path) != _sha256(task.source_md) or _sha256(match_path) != _sha256(task.structure_match):
        return False
    gate = run_local_gate(case=case, source_markdown=source, locked_structure=lock)
    return bool(gate.get("gate_passed"))


def _synthetic_gate(errors: list[str]) -> dict[str, Any]:
    return {"gate_passed": False, "blocking_issue_count": len(errors), "warning_count": 0, "blocking_issues": [{"issue_type": "pre_gate_validation", "message": error} for error in errors], "warnings": []}


def _write_gate(directory: Path, gate: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "local_gate_report.json", gate)
    (directory / "local_gate_report.md").write_text(render_local_gate_markdown(gate), encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

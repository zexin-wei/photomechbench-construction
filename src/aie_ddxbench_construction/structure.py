"""Stage 3 SMILES proposal, RDKit validation, visual identity review, and lock."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .chemistry import validate_smiles_with_rdkit
from .depiction import render_smiles
from .json_io import parse_json_object
from .prompting import load_prompt
from .provider import ModelClient

STRUCTURE_SYSTEM_PROMPT = (
    "You are a strict molecular-structure curator. Use only the supplied paper "
    "context and images. Return one JSON object without hidden reasoning."
)
PROPOSAL_PROMPT_VERSION = "smiles_proposal_v1"
IDENTITY_PROMPT_VERSION = "structure_identity_review_v1"
REPAIR_PROMPT_VERSION = "smiles_repair_v1"


@dataclass(frozen=True, slots=True)
class StructureTask:
    candidate_id: str
    doi: str
    molecule_label: str
    entity_type: str
    source_md: Path
    source_images: tuple[Path, ...]
    paper_title: str = ""
    structure_sources: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureResult:
    candidate_id: str
    status: str
    output_dir: Path
    locked_smiles: str | None = None
    error: str | None = None


def run_structure_resolution(
    task: StructureTask,
    *,
    output_dir: Path,
    client: ModelClient,
    resume: bool = False,
    allow_one_repair: bool = True,
    max_source_images: int = 5,
) -> StructureResult:
    """Resolve one candidate; only a confirmed visual identity creates a lock."""
    output_dir.mkdir(parents=True, exist_ok=True)
    input_hashes = _input_hashes(task)
    if resume:
        cached = _load_valid_lock(task.candidate_id, output_dir, input_hashes)
        if cached:
            return StructureResult(task.candidate_id, "skipped_valid", output_dir, cached)

    _write_json(output_dir / "task.json", {**asdict(task), "source_md": str(task.source_md), "source_images": [str(p) for p in task.source_images]})
    proposal_images = task.source_images[:max_source_images]
    proposal = _model_json(
        client,
        prompt=build_smiles_proposal_prompt(task),
        image_paths=proposal_images,
        output_dir=output_dir / "01_proposal",
        prompt_version=PROPOSAL_PROMPT_VERSION,
    )
    smiles = _proposed_smiles(proposal)
    attempt = _validate_render_review(task, smiles, output_dir=output_dir / "02_attempt", client=client)

    if attempt["status"] != "confirmed" and allow_one_repair:
        repair = _model_json(
            client,
            prompt=build_smiles_repair_prompt(task, proposal=proposal, failure=attempt),
            image_paths=(Path(str(attempt["structure_match_path"])),) if attempt.get("structure_match_path") else proposal_images,
            output_dir=output_dir / "03_repair",
            prompt_version=REPAIR_PROMPT_VERSION,
        )
        repaired_smiles = _proposed_smiles(repair)
        if repaired_smiles and repaired_smiles != smiles:
            attempt = _validate_render_review(task, repaired_smiles, output_dir=output_dir / "04_repaired_attempt", client=client)

    summary = {
        "candidate_id": task.candidate_id,
        "status": attempt["status"],
        "input_hashes": input_hashes,
        "attempt": attempt,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output_dir / "structure_resolution_summary.json", summary)
    if attempt["status"] != "confirmed":
        return StructureResult(task.candidate_id, "not_confirmed", output_dir, error=str(attempt.get("reason") or "identity not confirmed"))

    locked = str(attempt["canonical_smiles"])
    lock = {
        "lock_schema_version": "1.0",
        "candidate_id": task.candidate_id,
        "doi": task.doi,
        "molecule_label": task.molecule_label,
        "locked_smiles": locked,
        "final_structure_status": "validated",
        "unresolved_structure_concerns": [],
        "input_hashes": input_hashes,
        "rdkit_report": attempt["rdkit_report"],
        "identity_review": attempt["identity_review"],
        "structure_match_sha256": _sha256(Path(attempt["structure_match_path"])),
        "locked_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output_dir / "locked_structure.json", lock)
    final_match = output_dir / "structure_match.png"
    final_match.write_bytes(Path(attempt["structure_match_path"]).read_bytes())
    return StructureResult(task.candidate_id, "confirmed", output_dir, locked)


def build_smiles_proposal_prompt(task: StructureTask) -> str:
    source = _source_excerpt(task.source_md, 120_000)
    policy = load_prompt(PROPOSAL_PROMPT_VERSION)
    return f"""{policy}

Target:
{json.dumps(_task_metadata(task), ensure_ascii=False, indent=2)}

Paper source:
```markdown
{source}
```
"""


def build_identity_review_prompt(task: StructureTask, *, canonical_smiles: str) -> str:
    policy = load_prompt(IDENTITY_PROMPT_VERSION)
    return f"""{policy}

Target:
{json.dumps({**_task_metadata(task), "candidate_smiles": canonical_smiles}, ensure_ascii=False, indent=2)}
"""


def build_smiles_repair_prompt(task: StructureTask, *, proposal: dict[str, Any], failure: dict[str, Any]) -> str:
    policy = load_prompt(REPAIR_PROMPT_VERSION)
    return f"""{policy}

Target:
{json.dumps(_task_metadata(task), ensure_ascii=False, indent=2)}

Previous proposal:
{json.dumps(proposal, ensure_ascii=False, indent=2)}

Validation or identity failure:
{json.dumps(failure, ensure_ascii=False, indent=2)}
"""


def compose_structure_match(task: StructureTask, *, depiction_path: Path, output_path: Path) -> None:
    """Create the review image used both for identity review and Stage 5 audit."""
    panels: list[tuple[str, Image.Image]] = []
    for index, path in enumerate(task.source_images[:2], start=1):
        if path.is_file():
            panels.append((f"Source paper structure evidence {index}: {path.name}", Image.open(path).convert("RGB")))
    if not panels:
        panels.append(("Source paper structure evidence: missing", Image.new("RGB", (700, 450), "white")))
    panels.append(("RDKit depiction of candidate SMILES", Image.open(depiction_path).convert("RGB")))
    width = 900
    label_height = 42
    margin = 20
    fitted: list[tuple[str, Image.Image]] = []
    for label, image in panels:
        copy = image.copy()
        copy.thumbnail((width, 620), Image.Resampling.LANCZOS)
        fitted.append((label, copy))
    total_height = margin + sum(label_height + image.height + margin for _, image in fitted)
    canvas = Image.new("RGB", (width + margin * 2, total_height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    y = margin
    for label, image in fitted:
        draw.text((margin, y), label, fill="black", font=font)
        y += label_height
        canvas.paste(image, (margin + (width - image.width) // 2, y))
        y += image.height + margin
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _validate_render_review(task: StructureTask, smiles: str | None, *, output_dir: Path, client: ModelClient) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not smiles:
        return {"status": "no_smiles", "reason": "Model did not provide a supported SMILES."}
    rdkit = validate_smiles_with_rdkit(smiles)
    _write_json(output_dir / "rdkit_report.json", rdkit)
    canonical = rdkit.get("canonical_smiles")
    if not rdkit.get("rdkit_available"):
        return {"status": "rdkit_failed", "reason": "RDKit runtime was unavailable.", "proposed_smiles": smiles, "rdkit_report": rdkit}
    if not rdkit.get("sanitize_success") or not canonical or rdkit.get("blocking_issues"):
        return {"status": "rdkit_failed", "reason": "RDKit parse/sanitize validation failed.", "proposed_smiles": smiles, "rdkit_report": rdkit}
    depiction = output_dir / "rdkit_depiction.png"
    render_report = render_smiles(str(canonical), depiction)
    _write_json(output_dir / "depiction_report.json", render_report)
    structure_match = output_dir / "structure_match.png"
    compose_structure_match(task, depiction_path=depiction, output_path=structure_match)
    review = _model_json(
        client,
        prompt=build_identity_review_prompt(task, canonical_smiles=str(canonical)),
        image_paths=(structure_match,),
        output_dir=output_dir / "identity_review",
        prompt_version=IDENTITY_PROMPT_VERSION,
    )
    review["candidate_smiles"] = str(canonical)
    _write_json(output_dir / "identity_review.json", review)
    confirmed = (
        review.get("structure_match_status") == "confirmed_match"
        and review.get("final_stage3_decision") == "confirmed_smiles"
        and review.get("single_molecule_ok") is True
        and review.get("target_label_ok") is True
        and review.get("not_confused_with_other_paper_molecule") is True
    )
    return {
        "status": "confirmed" if confirmed else "identity_not_confirmed",
        "reason": review.get("recommended_next_action") or review.get("failure_mode"),
        "canonical_smiles": str(canonical),
        "rdkit_report": rdkit,
        "identity_review": review,
        "structure_match_path": str(structure_match),
    }


def _model_json(client: ModelClient, *, prompt: str, image_paths: tuple[Path, ...], output_dir: Path, prompt_version: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "request.json",
        {"prompt_version": prompt_version, "provider": client.provider_name, "model": client.model, "system_prompt": STRUCTURE_SYSTEM_PROMPT, "user_text": prompt, "image_names": [p.name for p in image_paths]},
    )
    (output_dir / "request.md").write_text(prompt, encoding="utf-8")
    response = client.complete(system_prompt=STRUCTURE_SYSTEM_PROMPT, user_text=prompt, image_paths=image_paths)
    (output_dir / "raw_response.txt").write_text(response.text, encoding="utf-8")
    parsed = parse_json_object(response.text)
    _write_json(output_dir / "result.json", parsed)
    return parsed


def _proposed_smiles(value: dict[str, Any]) -> str | None:
    smiles = value.get("proposed_smiles")
    return str(smiles).strip() if isinstance(smiles, str) and smiles.strip() else None


def _task_metadata(task: StructureTask) -> dict[str, Any]:
    return {"candidate_id": task.candidate_id, "doi": task.doi, "paper_title": task.paper_title, "molecule_label": task.molecule_label, "entity_type": task.entity_type, "structure_sources": list(task.structure_sources), "risk_flags": list(task.risk_flags)}


def _source_excerpt(path: Path, limit: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit] + "\n[...SOURCE TRUNCATED...]"


def _input_hashes(task: StructureTask) -> dict[str, str]:
    return {"source.md": _sha256(task.source_md), **{f"source_image_{i}": _sha256(path) for i, path in enumerate(task.source_images, start=1)}}


def _load_valid_lock(candidate_id: str, output_dir: Path, input_hashes: dict[str, str]) -> str | None:
    lock_path = output_dir / "locked_structure.json"
    match_path = output_dir / "structure_match.png"
    if not lock_path.is_file() or not match_path.is_file():
        return None
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if lock.get("candidate_id") != candidate_id or lock.get("input_hashes") != input_hashes:
        return None
    if lock.get("structure_match_sha256") != _sha256(match_path):
        return None
    smiles = str(lock.get("locked_smiles") or "")
    report = validate_smiles_with_rdkit(smiles)
    return smiles if smiles and report.get("sanitize_success") and not report.get("blocking_issues") else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

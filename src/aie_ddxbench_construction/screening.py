"""Canonical paper-level screening and molecule-candidate extraction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .json_io import parse_json_object
from .mechanism_profiles import load_mechanism_profile
from .prompting import load_prompt
from .provider import ModelClient
from .vocabulary import OFFICIAL_MECHANISMS

SCREENING_SYSTEM_PROMPT = (
    "You are a strict scientific data curator for PhotoMechBench. "
    "Use only the supplied source material. Return exactly one JSON object, "
    "without hidden reasoning, markdown fences, or invented evidence."
)
PAPER_SCREEN_PROMPT_VERSION = "paper_screen_v1"
CANDIDATE_SCREEN_PROMPT_VERSION = "candidate_screen_v1"
PAPER_VERDICTS = {"pass", "fail"}
CONCRETE_UNIT_TYPES = {"molecule", "probe", "ligand", "guest"}
CANDIDATE_ELIGIBILITY = {"pass", "fail"}


@dataclass(frozen=True, slots=True)
class ParsedPaper:
    doi: str
    source_md: Path
    title: str = ""
    pdf_name: str = ""


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    status: str
    output_dir: Path
    parsed: dict[str, Any] | None = None
    error: str | None = None


def build_paper_screen_prompt(
    paper: ParsedPaper,
    *,
    retrieval_mechanism: str,
    image_candidates: list[dict[str, Any]] | None = None,
    source_char_limit: int = 120_000,
) -> str:
    _require_mechanism(retrieval_mechanism)
    source = _source_excerpt(paper.source_md, source_char_limit)
    metadata = {"doi": paper.doi, "title": paper.title, "pdf_name": paper.pdf_name}
    policy = load_prompt(PAPER_SCREEN_PROMPT_VERSION)
    return f"""{policy}

Paper metadata:
{json.dumps(metadata, ensure_ascii=False, indent=2)}

Retrieval mechanism hypothesis: {retrieval_mechanism}

Parsed image references and nearby caption context:
{json.dumps(image_candidates or [], ensure_ascii=False, indent=2)}

Parsed source:
```markdown
{source}
```
"""


def build_candidate_screen_prompt(
    paper: ParsedPaper,
    *,
    retrieval_mechanism: str,
    paper_review: dict[str, Any],
    image_candidates: list[dict[str, Any]] | None = None,
    source_char_limit: int = 160_000,
) -> str:
    _require_mechanism(retrieval_mechanism)
    source = _source_excerpt(paper.source_md, source_char_limit)
    profile = load_mechanism_profile(retrieval_mechanism)
    policy = load_prompt(CANDIDATE_SCREEN_PROMPT_VERSION)
    return f"""{policy}

Paper metadata:
{json.dumps({"doi": paper.doi, "title": paper.title, "pdf_name": paper.pdf_name}, ensure_ascii=False, indent=2)}

Official mechanism vocabulary:
{json.dumps(list(OFFICIAL_MECHANISMS), ensure_ascii=False, indent=2)}

Retrieval mechanism profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Stage 1 review:
{json.dumps(paper_review, ensure_ascii=False, indent=2)}

Available image references:
{json.dumps(image_candidates or [], ensure_ascii=False, indent=2)}

Parsed source:
```markdown
{source}
```
"""


def run_paper_screen(
    paper: ParsedPaper,
    *,
    retrieval_mechanism: str,
    output_dir: Path,
    client: ModelClient,
    image_candidates: list[dict[str, Any]] | None = None,
    resume: bool = False,
) -> ScreeningResult:
    prompt = build_paper_screen_prompt(
        paper,
        retrieval_mechanism=retrieval_mechanism,
        image_candidates=image_candidates,
    )
    return _run_screen(
        stage="paper_screen",
        prompt_version=PAPER_SCREEN_PROMPT_VERSION,
        prompt=prompt,
        output_dir=output_dir,
        client=client,
        source_path=paper.source_md,
        validator=validate_paper_review,
        resume=resume,
    )


def run_candidate_screen(
    paper: ParsedPaper,
    *,
    retrieval_mechanism: str,
    paper_review: dict[str, Any],
    output_dir: Path,
    client: ModelClient,
    image_candidates: list[dict[str, Any]] | None = None,
    contact_sheets: tuple[Path, ...] = (),
    resume: bool = False,
) -> ScreeningResult:
    prompt = build_candidate_screen_prompt(
        paper,
        retrieval_mechanism=retrieval_mechanism,
        paper_review=paper_review,
        image_candidates=image_candidates,
    )
    return _run_screen(
        stage="candidate_screen",
        prompt_version=CANDIDATE_SCREEN_PROMPT_VERSION,
        prompt=prompt,
        output_dir=output_dir,
        client=client,
        source_path=paper.source_md,
        validator=lambda value: validate_candidate_review(
            value,
            allowed_image_ids={str(row["image_id"]) for row in image_candidates or []},
        ),
        resume=resume,
        image_paths=contact_sheets,
    )


def validate_paper_review(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    verdict = value.get("paper_verdict")
    if verdict not in PAPER_VERDICTS:
        errors.append(f"invalid paper_verdict: {verdict!r}")
    units = value.get("candidate_units")
    if not isinstance(units, list):
        errors.append("candidate_units must be an array")
    reason = value.get("failure_reason_type")
    if verdict == "fail" and reason in {None, "", "not_failed"}:
        errors.append("fail requires a specific failure_reason_type")
    if verdict == "pass" and reason != "not_failed":
        errors.append("pass requires failure_reason_type=not_failed")
    recommendations = value.get("recommended_image_ids")
    if not isinstance(recommendations, list) or not all(isinstance(item, str) for item in recommendations):
        errors.append("recommended_image_ids must be an array of image IDs")
    elif len(recommendations) > 12:
        errors.append("recommended_image_ids may contain at most 12 IDs")
    return errors


def validate_candidate_review(
    value: dict[str, Any],
    *,
    allowed_image_ids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if value.get("target_discovery_mechanism") not in OFFICIAL_MECHANISMS:
        errors.append("target_discovery_mechanism must use the official mechanism vocabulary")
    units = value.get("candidate_units")
    if not isinstance(units, list):
        return ["candidate_units must be an array"]
    for index, unit in enumerate(units):
        prefix = f"candidate_units[{index}]"
        if not isinstance(unit, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if unit.get("unit_type") not in CONCRETE_UNIT_TYPES | {"unclear"}:
            errors.append(f"{prefix}.unit_type is invalid")
        if unit.get("eligibility") not in CANDIDATE_ELIGIBILITY:
            errors.append(f"{prefix}.eligibility is invalid")
        if unit.get("eligibility") == "pass" and unit.get("unit_type") not in CONCRETE_UNIT_TYPES:
            errors.append(f"{prefix}: pass requires a concrete single-molecule unit_type")
        image_ids = unit.get("structure_image_ids")
        if not isinstance(image_ids, list) or not all(isinstance(item, str) for item in image_ids):
            errors.append(f"{prefix}.structure_image_ids must be an array of image IDs")
        elif len(image_ids) > 2:
            errors.append(f"{prefix}.structure_image_ids may contain at most two IDs")
        elif allowed_image_ids is not None:
            unknown = [item for item in image_ids if item not in allowed_image_ids]
            if unknown:
                errors.append(f"{prefix}.structure_image_ids contains unavailable IDs: {unknown}")
        text_sources = unit.get("structure_text_sources")
        if not isinstance(text_sources, list) or not all(isinstance(item, str) for item in text_sources):
            errors.append(f"{prefix}.structure_text_sources must be an array of strings")
        assignments = unit.get("official_mechanism_assignments", [])
        if not isinstance(assignments, list):
            errors.append(f"{prefix}.official_mechanism_assignments must be an array")
            continue
        for assignment in assignments:
            mechanism = assignment.get("mechanism") if isinstance(assignment, dict) else None
            if mechanism not in OFFICIAL_MECHANISMS:
                errors.append(f"{prefix}: non-official mechanism assignment {mechanism!r}")
    return errors


def candidate_manifest_rows(reviews: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for review in reviews:
        for unit in review.get("candidate_units", []):
            if not isinstance(unit, dict):
                continue
            if unit.get("unit_type") not in CONCRETE_UNIT_TYPES:
                continue
            if unit.get("eligibility") != "pass":
                continue
            label = str(unit.get("unit_label") or "").strip()
            if not label:
                continue
            rows.append(
                {
                    "paper_title": review.get("paper_title"),
                    "retrieval_mechanism": review.get("target_discovery_mechanism"),
                    "molecule_label": label,
                    "entity_type": unit.get("unit_type"),
                    "eligibility": unit.get("eligibility"),
                    "stage3_risk_flags": unit.get("stage3_risk_flags", []),
                    "structure_image_ids": unit.get("structure_image_ids", []),
                    "structure_text_sources": unit.get("structure_text_sources", []),
                    "official_mechanism_assignments": unit.get("official_mechanism_assignments", []),
                    "confidence": unit.get("confidence"),
                    "reason": unit.get("reason"),
                }
            )
    return rows


def _run_screen(
    *,
    stage: str,
    prompt_version: str,
    prompt: str,
    output_dir: Path,
    client: ModelClient,
    source_path: Path,
    validator: Any,
    resume: bool,
    image_paths: tuple[Path, ...] = (),
) -> ScreeningResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_hash = _input_sha256(source_path, image_paths)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if resume:
        cached = _load_valid_result(
            output_dir,
            stage=stage,
            input_hash=input_hash,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            validator=validator,
        )
        if cached is not None:
            return ScreeningResult("skipped_valid", output_dir, cached)
    request = {
        "request_schema_version": "1.0",
        "stage": stage,
        "prompt_version": prompt_version,
        "provider": client.provider_name,
        "model": client.model,
        "source_sha256": input_hash,
        "prompt_sha256": prompt_hash,
        "system_prompt": SCREENING_SYSTEM_PROMPT,
        "user_text": prompt,
        "image_names": [path.name for path in image_paths],
    }
    _write_json(output_dir / "request.json", request)
    (output_dir / "request.md").write_text(prompt, encoding="utf-8")
    try:
        response = client.complete(system_prompt=SCREENING_SYSTEM_PROMPT, user_text=prompt, image_paths=image_paths)
        (output_dir / "raw_response.txt").write_text(response.text, encoding="utf-8")
        parsed = parse_json_object(response.text)
        errors = validator(parsed)
        if errors:
            raise ValueError("; ".join(errors))
        _write_json(output_dir / "result.json", parsed)
        _write_json(
            output_dir / "response.json",
            {
                "success": True,
                "provider": client.provider_name,
                "requested_model": client.model,
                "response_id": response.response_id,
                "response_model": response.response_model,
                "usage": response.usage,
                "source_sha256": input_hash,
                "result_sha256": _sha256(output_dir / "result.json"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return ScreeningResult("completed", output_dir, parsed)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        _write_json(
            output_dir / "response.json",
            {"success": False, "source_sha256": input_hash, "error": error, "failed_at": datetime.now(timezone.utc).isoformat()},
        )
        return ScreeningResult("failed", output_dir, error=error)


def _load_valid_result(
    output_dir: Path,
    *,
    stage: str,
    input_hash: str,
    prompt_version: str,
    prompt_hash: str,
    validator: Any,
) -> dict[str, Any] | None:
    request_path = output_dir / "request.json"
    response_path = output_dir / "response.json"
    result_path = output_dir / "result.json"
    if not all(path.is_file() for path in (request_path, response_path, result_path)):
        return None
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        request.get("stage") != stage
        or request.get("source_sha256") != input_hash
        or request.get("prompt_version") != prompt_version
        or request.get("prompt_sha256") != prompt_hash
    ):
        return None
    if response.get("success") is not True or response.get("source_sha256") != input_hash:
        return None
    if response.get("result_sha256") != _sha256(result_path) or validator(result):
        return None
    return result


def _source_excerpt(path: Path, limit: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if limit <= 0 or len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    return text[:head] + "\n\n[...SOURCE TRUNCATED...]\n\n" + text[-tail:]


def _require_mechanism(mechanism: str) -> None:
    if mechanism not in OFFICIAL_MECHANISMS:
        raise ValueError(f"Unknown mechanism: {mechanism}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_sha256(source_path: Path, image_paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256(_sha256(source_path).encode("ascii"))
    for path in image_paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(_sha256(path).encode("ascii"))
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

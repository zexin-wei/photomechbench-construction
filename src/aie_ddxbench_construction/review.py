"""Independent three-artifact review with verifiable resume semantics."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .prompting import (
    INDEPENDENT_REVIEW_PROMPT_VERSION,
    INDEPENDENT_REVIEW_SYSTEM_PROMPT,
    build_independent_review_text,
)
from .provider import ModelClient
from .vocabulary import REVIEW_DECISIONS

DECISION_PATTERN = re.compile(
    r"(?im)^\s*overall_decision\s*:\s*(NEEDS_MINOR_FIX|FAIL_OR_REBUILD|PASS)\s*$"
)


@dataclass(frozen=True, slots=True)
class ReviewCase:
    case_id: str
    archive_mechanism: str
    case_json: Path
    source_md: Path
    structure_match: Path

    @classmethod
    def from_directory(cls, case_dir: Path, *, archive_mechanism: str | None = None) -> "ReviewCase":
        case_json = case_dir / "final_reference_alignment.json"
        source_md = case_dir / "source.md"
        structure_match = case_dir / "structure_match.png"
        missing = [path.name for path in (case_json, source_md, structure_match) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing review artifact(s) in {case_dir}: {', '.join(missing)}")
        parsed = json.loads(case_json.read_text(encoding="utf-8-sig"))
        case_id = str(parsed.get("case_id") or case_dir.name)
        mechanism = archive_mechanism or case_dir.parent.name
        return cls(case_id, mechanism, case_json, source_md, structure_match)


@dataclass(frozen=True, slots=True)
class ReviewResult:
    case_id: str
    status: str
    decision: str | None
    output_dir: Path
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "decision": self.decision,
            "output_dir": str(self.output_dir),
            "error": self.error,
        }


def run_independent_review(
    case: ReviewCase,
    *,
    output_dir: Path,
    client: ModelClient,
    resume: bool = False,
) -> ReviewResult:
    """Review one case and preserve the exact request text and input hashes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_text = case.case_json.read_text(encoding="utf-8-sig")
    source_text = case.source_md.read_text(encoding="utf-8", errors="replace")
    request_text = build_independent_review_text(
        case_name=case.case_id,
        archive_mechanism=case.archive_mechanism,
        case_json_text=json_text,
        source_text=source_text,
        include_image=True,
    )
    request_record = {
        "request_schema_version": "1.0",
        "prompt_version": INDEPENDENT_REVIEW_PROMPT_VERSION,
        "provider": client.provider_name,
        "model": client.model,
        "prompt_sha256": hashlib.sha256(
            (INDEPENDENT_REVIEW_SYSTEM_PROMPT + "\0" + request_text).encode("utf-8")
        ).hexdigest(),
        "system_prompt": INDEPENDENT_REVIEW_SYSTEM_PROMPT,
        "user_text": request_text,
        "inputs": {
            "final_reference_alignment.json": _file_record(case.case_json),
            "source.md": _file_record(case.source_md),
            "structure_match.png": _file_record(case.structure_match),
        },
    }
    if resume:
        existing = load_valid_review_result(
            case.case_id,
            output_dir,
            expected_request=request_record,
        )
        if existing is not None:
            return ReviewResult(case.case_id, "skipped_valid", existing, output_dir)
    _write_json(output_dir / "request.json", request_record)
    (output_dir / "request.md").write_text(request_text, encoding="utf-8")

    response = None
    try:
        response = client.complete(
            system_prompt=INDEPENDENT_REVIEW_SYSTEM_PROMPT,
            user_text=request_text,
            image_paths=(case.structure_match,),
        )
        (output_dir / "raw_response.txt").write_text(response.text, encoding="utf-8")
        decision = parse_review_decision(response.text)
        if decision is None:
            raise ValueError("Model response did not contain a valid overall_decision.")
        (output_dir / "review.md").write_text(response.text, encoding="utf-8")
        response_record = {
            "success": True,
            "decision": decision,
            "provider": client.provider_name,
            "requested_model": client.model,
            "response_id": response.response_id,
            "response_model": response.response_model,
            "usage": response.usage,
            "response_metadata": response.metadata,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "raw_response_sha256": _sha256(output_dir / "raw_response.txt"),
        }
        _write_json(output_dir / "response.json", response_record)
        _write_json(output_dir / "review_summary.json", {"case_id": case.case_id, "decision": decision})
        return ReviewResult(case.case_id, "completed", decision, output_dir)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raw_path = output_dir / "raw_response.txt"
        _write_json(
            output_dir / "response.json",
            {
                "success": False,
                "provider": client.provider_name,
                "requested_model": client.model,
                "error": error,
                "response_id": response.response_id if response else None,
                "response_model": response.response_model if response else None,
                "usage": response.usage if response else None,
                "response_metadata": response.metadata if response else None,
                "raw_response_sha256": _sha256(raw_path) if raw_path.is_file() else None,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return ReviewResult(case.case_id, "failed", None, output_dir, error)


def run_review_batch(
    cases: Iterable[ReviewCase],
    *,
    output_root: Path,
    client: ModelClient,
    resume: bool = False,
    keep_going: bool = False,
) -> list[ReviewResult]:
    results: list[ReviewResult] = []
    for case in cases:
        case_output = output_root / case.archive_mechanism / case.case_id
        result = run_independent_review(case, output_dir=case_output, client=client, resume=resume)
        results.append(result)
        if result.status == "failed" and not keep_going:
            break
    _write_json(
        output_root / "review_batch_summary.json",
        {
            "case_count": len(results),
            "results": [result.to_dict() for result in results],
        },
    )
    return results


def parse_review_decision(text: str) -> str | None:
    match = DECISION_PATTERN.search(text or "")
    if not match:
        return None
    decision = match.group(1)
    return decision if decision in REVIEW_DECISIONS else None


def load_valid_review_result(
    case_id: str,
    output_dir: Path,
    *,
    expected_request: dict[str, Any] | None = None,
) -> str | None:
    request_path = output_dir / "request.json"
    summary_path = output_dir / "review_summary.json"
    response_path = output_dir / "response.json"
    raw_path = output_dir / "raw_response.txt"
    review_path = output_dir / "review.md"
    if not all(path.is_file() for path in (request_path, summary_path, response_path, raw_path, review_path)):
        return None
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        response = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    decision = summary.get("decision")
    if summary.get("case_id") != case_id or decision not in REVIEW_DECISIONS or response.get("success") is not True:
        return None
    if expected_request is not None:
        for key in ("prompt_version", "provider", "model", "prompt_sha256", "inputs"):
            if request.get(key) != expected_request.get(key):
                return None
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    if parse_review_decision(raw_text) != decision:
        return None
    if response.get("raw_response_sha256") != _sha256(raw_path):
        return None
    return str(decision)


def _file_record(path: Path) -> dict[str, Any]:
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

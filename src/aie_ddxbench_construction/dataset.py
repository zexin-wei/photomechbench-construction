"""Dataset-level identity audit and accepted-case release packaging."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .identity import structure_identity
from .literature import normalize_doi
from .review import parse_review_decision
from .schema import validate_raw_case
from .vocabulary import ACCEPTED_REVIEW_DECISIONS, OFFICIAL_MECHANISM_SET


@dataclass(frozen=True, slots=True)
class ReleaseCase:
    archive_mechanism: str
    case_dir: Path
    review_dir: Path


def audit_release_cases(cases: Iterable[ReleaseCase]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for item in cases:
        json_path = item.case_dir / "final_reference_alignment.json"
        source_path = item.case_dir / "source.md"
        image_path = item.case_dir / "structure_match.png"
        missing = [path.name for path in (json_path, source_path, image_path) if not path.is_file()]
        if missing:
            blockers.append({"case_id": item.case_dir.name, "issue_type": "missing_artifacts", "missing": missing})
            continue
        try:
            case = json.loads(json_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            blockers.append({"case_id": item.case_dir.name, "issue_type": "invalid_json", "message": str(exc)})
            continue
        case_id = str(case.get("case_id") or item.case_dir.name)
        issues = validate_raw_case(case)
        decision = _review_decision(item.review_dir)
        if issues:
            blockers.append({"case_id": case_id, "issue_type": "schema_invalid", "issues": [issue.to_dict() for issue in issues]})
        if decision not in ACCEPTED_REVIEW_DECISIONS:
            blockers.append({"case_id": case_id, "issue_type": "review_not_accepted", "decision": decision})
        if item.archive_mechanism not in OFFICIAL_MECHANISM_SET:
            blockers.append({"case_id": case_id, "issue_type": "invalid_archive_mechanism", "mechanism": item.archive_mechanism})
        source = (case.get("hidden_reference") or {}).get("source_article") or {}
        smiles = str((((case.get("public_input") or {}).get("molecule") or {}).get("structure") or {}).get("value") or "")
        try:
            identity = structure_identity(smiles)
        except Exception as exc:
            identity = {"parse_success": False, "error": f"{type(exc).__name__}: {exc}"}
        if not identity.get("parse_success"):
            blockers.append({"case_id": case_id, "issue_type": "identity_key_failed", "details": identity})
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        doi = normalize_doi(source.get("doi"))
        source_dois = sorted({normalize_doi(match) for match in re.findall(r"\b10\.\d{4,9}/[^\s<>\]\[\"'`{}|\\]+", source_text, re.IGNORECASE)})
        if doi and source_dois and doi not in source_dois:
            blockers.append({"case_id": case_id, "issue_type": "json_source_doi_mismatch", "json_doi": doi, "source_dois": source_dois})
        rows.append(
            {
                "case_id": case_id,
                "archive_mechanism": item.archive_mechanism,
                "decision": decision,
                "doi": doi,
                "molecule_label": str(source.get("molecule_label") or ""),
                "label_key": _normalize_label(source.get("molecule_label")),
                "smiles": smiles,
                **identity,
                "case_dir": str(item.case_dir),
                "review_dir": str(item.review_dir),
            }
        )
    duplicate_groups = _duplicates(rows)
    blockers.extend(group for group in duplicate_groups if group["blocking"])
    return {
        "report_name": "release_identity_duplicate_audit",
        "case_count": len(rows),
        "blocker_count": len(blockers),
        "duplicate_group_count": len(duplicate_groups),
        "passed": not blockers and bool(rows),
        "rows": rows,
        "duplicate_groups": duplicate_groups,
        "blockers": blockers,
    }


def package_accepted_cases(cases: Iterable[ReleaseCase], *, output_dir: Path) -> dict[str, Any]:
    items = list(cases)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    audit = audit_release_cases(items)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "prepackage_audit.json", audit)
    if not audit["passed"]:
        raise ValueError(f"Prepackage audit failed with {audit['blocker_count']} blocker(s).")
    count = len(items)
    submission = output_dir / f"submission_json_{count}"
    internal = output_dir / f"internal_provenance_and_reviews_{count}"
    manifest_rows: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: (row.archive_mechanism, row.case_dir.name)):
        case_json = item.case_dir / "final_reference_alignment.json"
        case = json.loads(case_json.read_text(encoding="utf-8-sig"))
        case_id = str(case["case_id"])
        json_out = submission / item.archive_mechanism / f"{case_id}.json"
        json_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(case_json, json_out)
        provenance_out = internal / "cases" / item.archive_mechanism / case_id
        provenance_out.mkdir(parents=True, exist_ok=True)
        for name in ("final_reference_alignment.json", "source.md", "structure_match.png", "locked_structure.json"):
            source = item.case_dir / name
            if source.is_file():
                shutil.copy2(source, provenance_out / name)
        review_out = internal / "stage5_reviews" / item.archive_mechanism / case_id
        shutil.copytree(item.review_dir, review_out)
        manifest_rows.append(
            {
                "case_id": case_id,
                "archive_mechanism": item.archive_mechanism,
                "review_decision": _review_decision(item.review_dir),
                "submission_json": str(json_out.relative_to(output_dir)),
                "submission_sha256": _sha256(json_out),
                "provenance_dir": str(provenance_out.relative_to(output_dir)),
                "review_dir": str(review_out.relative_to(output_dir)),
            }
        )
    _write_json(internal / "release_manifest.json", {"case_count": count, "cases": manifest_rows})
    _write_json(internal / "identity_duplicate_audit.json", audit)
    return {"case_count": count, "submission_root": str(submission), "internal_root": str(internal), "manifest": manifest_rows}


def _duplicates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = (
        (("structure_key",), "exact_structure", True),
        (("doi", "label_key"), "same_paper_same_label", True),
        (("doi", "largest_fragment_key"), "same_paper_same_largest_fragment", False),
    )
    emitted: set[tuple[str, ...]] = set()
    groups: list[dict[str, Any]] = []
    for fields, kind, blocking in specs:
        index: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = tuple(str(row.get(field) or "") for field in fields)
            if all(key):
                index[key].append(row)
        for key, members in index.items():
            case_ids = tuple(sorted(str(row["case_id"]) for row in members))
            if len(members) < 2 or case_ids in emitted:
                continue
            if kind == "exact_structure" and len({str(row.get("doi") or "") for row in members}) > 1:
                blocking = True
            emitted.add(case_ids)
            groups.append({"issue_type": "duplicate_group", "duplicate_type": kind, "blocking": blocking, "key": list(key), "case_ids": list(case_ids), "archive_mechanisms": sorted({str(row["archive_mechanism"]) for row in members})})
    return groups


def _review_decision(review_dir: Path) -> str | None:
    summary = review_dir / "review_summary.json"
    if summary.is_file():
        try:
            value = json.loads(summary.read_text(encoding="utf-8"))
            decision = value.get("decision")
            if decision:
                return str(decision)
        except Exception:
            pass
    for name in ("review.md", "raw_response.txt"):
        path = review_dir / name
        if path.is_file():
            decision = parse_review_decision(path.read_text(encoding="utf-8", errors="replace"))
            if decision:
                return decision
    return None


def _normalize_label(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

"""Manifest-driven canonical batch runner for paper and raw-case stages."""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .image_catalog import (
    build_image_catalog,
    discover_image_paths,
    prompt_image_records,
    render_contact_sheets,
    select_catalog_records,
)
from .mineru_api import parse_pdf_with_mineru_vlm
from .provider import ModelClient
from .repair import run_minor_repair
from .reference import ReferenceTask, run_reference_construction
from .review import ReviewCase, run_independent_review
from .screening import ParsedPaper, candidate_manifest_rows, run_candidate_screen, run_paper_screen
from .structure import StructureTask, run_structure_resolution
from .vocabulary import OFFICIAL_MECHANISM_SET

STOP_STAGES = {"paper_screen", "candidate_screen", "structure", "reference", "review"}


def run_manifest_pipeline(
    manifest_path: Path,
    *,
    output_root: Path,
    client: ModelClient,
    resume: bool = False,
    keep_going: bool = False,
    stop_after: str = "review",
    mineru_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run selected stages from one path-neutral JSON manifest."""
    if stop_after not in STOP_STAGES:
        raise ValueError(f"Unknown stop_after stage: {stop_after}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    validate_pipeline_manifest(manifest)
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    paper_reviews: dict[str, dict[str, Any]] = {}
    candidate_reviews: list[dict[str, Any]] = []
    candidate_reviews_by_paper: list[tuple[str, dict[str, Any]]] = []
    image_catalogs: dict[str, dict[str, Any]] = {}

    for row in manifest.get("papers", []):
        paper_id = str(row["paper_id"])
        mechanism = str(row["retrieval_mechanism"])
        paper_root = output_root / "papers" / paper_id
        if row.get("source_pdf"):
            if not mineru_options or not mineru_options.get("token"):
                raise ValueError(
                    f"Paper {paper_id} uses source_pdf, but no MinerU API token was supplied."
                )
            try:
                parse_report = parse_pdf_with_mineru_vlm(
                    _resolve(manifest_path, row["source_pdf"]),
                    output_dir=paper_root / "00_mineru",
                    resume=resume,
                    **mineru_options,
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                results.append({"item_type": "paper", "item_id": paper_id, "stage": "mineru_vlm", "status": "failed", "error": error})
                if not keep_going:
                    break
                continue
            results.append({"item_type": "paper", "item_id": paper_id, "stage": "mineru_vlm", "status": "completed", "error": None})
            row["source_md"] = str(parse_report["source_markdown"])
            row["source_image_dir"] = str(parse_report["source_image_dir"])
            row.setdefault("pdf_name", Path(str(row["source_pdf"])).name)
        paper = ParsedPaper(str(row["doi"]), _resolve(manifest_path, row["source_md"]), str(row.get("title") or ""), str(row.get("pdf_name") or ""))
        image_paths = discover_image_paths(
            source_images=(_resolve(manifest_path, value) for value in row.get("source_images", [])),
            source_image_dir=_resolve(manifest_path, row["source_image_dir"]) if row.get("source_image_dir") else None,
        )
        image_catalog = build_image_catalog(paper.source_md, image_paths)
        image_catalogs[paper_id] = image_catalog
        _write_json(paper_root / "00_image_catalog" / "image_catalog.json", image_catalog)
        compact_images = prompt_image_records(image_catalog)
        stage1 = run_paper_screen(
            paper,
            retrieval_mechanism=mechanism,
            output_dir=paper_root / "01_paper_screen",
            client=client,
            image_candidates=compact_images,
            resume=resume,
        )
        results.append({"item_type": "paper", "item_id": paper_id, "stage": "paper_screen", "status": stage1.status, "error": stage1.error})
        if stage1.status == "failed":
            if not keep_going:
                break
            continue
        paper_reviews[paper_id] = stage1.parsed or {}
        if stop_after == "paper_screen" or (stage1.parsed or {}).get("paper_verdict") == "reject":
            continue
        recommended_ids = list((stage1.parsed or {}).get("recommended_image_ids") or [])[:12]
        selected_records, unknown_ids = select_catalog_records(image_catalog, recommended_ids)
        fallback_used = False
        if not selected_records and image_catalog.get("images"):
            selected_records = list(image_catalog["images"][:12])
            fallback_used = True
        contact_sheets = render_contact_sheets(
            selected_records,
            output_dir=paper_root / "00_image_catalog" / "stage2_contact_sheets",
        )
        image_candidates = [
            row for row in prompt_image_records({"images": selected_records})
        ]
        _write_json(
            paper_root / "00_image_catalog" / "stage1_image_selection.json",
            {
                "recommended_image_ids": recommended_ids,
                "unknown_recommended_image_ids": unknown_ids,
                "stage2_image_ids": [record["image_id"] for record in selected_records],
                "fallback_to_first_images": fallback_used,
                "contact_sheets": [str(path) for path in contact_sheets],
            },
        )
        stage2 = run_candidate_screen(
            paper,
            retrieval_mechanism=mechanism,
            paper_review=stage1.parsed or {},
            output_dir=paper_root / "02_candidate_screen",
            client=client,
            image_candidates=image_candidates,
            contact_sheets=contact_sheets,
            resume=resume,
        )
        results.append({"item_type": "paper", "item_id": paper_id, "stage": "candidate_screen", "status": stage2.status, "error": stage2.error})
        if stage2.parsed:
            candidate_reviews.append(stage2.parsed)
            candidate_reviews_by_paper.append((paper_id, stage2.parsed))
        if stage2.status == "failed" and not keep_going:
            break

    _write_json(output_root / "candidate_manifest.json", {"rows": candidate_manifest_rows(candidate_reviews)})
    explicit_cases = list(manifest.get("cases", []))
    automatic = build_automatic_case_rows(
        manifest,
        candidate_reviews_by_paper,
        existing_cases=explicit_cases,
        image_catalogs=image_catalogs,
    )
    _write_json(output_root / "automatic_case_manifest.json", automatic)
    if stop_after in {"paper_screen", "candidate_screen"}:
        return _finish(output_root, results)

    paper_index = {str(row["paper_id"]): row for row in manifest.get("papers", [])}
    case_rows = [*explicit_cases, *automatic["promoted"]]
    for row in case_rows:
        case_id = str(row["case_id"])
        candidate_id = str(row["candidate_id"])
        paper_row = paper_index[str(row["paper_id"])]
        source_md = _resolve(manifest_path, paper_row["source_md"])
        images = tuple(_resolve(manifest_path, value) for value in row.get("structure_images", paper_row.get("source_images", [])))
        case_root = output_root / "cases" / case_id
        try:
            structure = run_structure_resolution(
                StructureTask(candidate_id, str(paper_row["doi"]), str(row["molecule_label"]), str(row.get("entity_type") or "molecule"), source_md, images, str(paper_row.get("title") or ""), tuple(row.get("structure_sources", [])), tuple(row.get("risk_flags", []))),
                output_dir=case_root / "03_structure",
                client=client,
                resume=resume,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            results.append({"item_type": "case", "item_id": case_id, "stage": "structure", "status": "failed", "error": error})
            if not keep_going:
                break
            continue
        results.append({"item_type": "case", "item_id": case_id, "stage": "structure", "status": structure.status, "error": structure.error})
        if structure.status not in {"confirmed", "skipped_valid"}:
            if not keep_going:
                break
            continue
        if stop_after == "structure":
            continue
        structure_dir = case_root / "03_structure"
        reference = run_reference_construction(
            ReferenceTask(case_id, source_md, structure_dir / "locked_structure.json", structure_dir / "structure_match.png", dict(row["source_article"]), dict(row.get("target_context") or {})),
            output_dir=case_root / "04_reference",
            client=client,
            resume=resume,
        )
        results.append({"item_type": "case", "item_id": case_id, "stage": "reference", "status": reference.status, "error": reference.error})
        if reference.status not in {"completed", "skipped_valid"}:
            if not keep_going:
                break
            continue
        if stop_after == "reference":
            continue
        delivery = case_root / "04_reference" / "delivery"
        review_case = ReviewCase.from_directory(delivery, archive_mechanism=str(row["archive_mechanism"]))
        review = run_independent_review(review_case, output_dir=case_root / "05_review", client=client, resume=resume)
        results.append({"item_type": "case", "item_id": case_id, "stage": "review", "status": review.status, "decision": review.decision, "error": review.error})
        if review.status == "failed" and not keep_going:
            break
        if review.decision == "NEEDS_MINOR_FIX":
            lock_path = structure_dir / "locked_structure.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            try:
                repair = run_minor_repair(
                    original_case_path=delivery / "final_reference_alignment.json",
                    source_path=delivery / "source.md",
                    structure_match_path=delivery / "structure_match.png",
                    review_path=case_root / "05_review" / "review.md",
                    locked_structure=lock,
                    output_dir=case_root / "06_minor_repair",
                    client=client,
                    max_gate_repair_rounds=1,
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                results.append({"item_type": "case", "item_id": case_id, "stage": "minor_repair", "status": "failed", "error": error})
                if not keep_going:
                    break
                continue
            results.append({"item_type": "case", "item_id": case_id, "stage": "minor_repair", "status": repair.status, "error": "; ".join(repair.validation_errors) or None})
            if repair.packaged_for_rereview:
                repaired_case = ReviewCase.from_directory(repair.output_dir / "rereview_input", archive_mechanism=str(row["archive_mechanism"]))
                rereview = run_independent_review(repaired_case, output_dir=case_root / "07_rereview", client=client, resume=resume)
                results.append({"item_type": "case", "item_id": case_id, "stage": "rereview", "status": rereview.status, "decision": rereview.decision, "error": rereview.error})
                if rereview.status == "failed" and not keep_going:
                    break
            elif not keep_going:
                break
    return _finish(output_root, results)


def build_automatic_case_rows(
    manifest: dict[str, Any],
    candidate_reviews: list[tuple[str, dict[str, Any]]],
    *,
    existing_cases: list[dict[str, Any]] | None = None,
    image_catalogs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Promote unambiguous Stage 2 make_case units into deterministic case rows."""
    paper_index = {str(row["paper_id"]): row for row in manifest.get("papers", [])}
    existing_cases = existing_cases or []
    image_catalogs = image_catalogs or {}
    occupied_ids = {str(row.get("case_id") or "") for row in existing_cases}
    occupied_targets = {
        (str(row.get("paper_id") or ""), _normalized_label(row.get("molecule_label")))
        for row in existing_cases
    }
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for paper_id, review in candidate_reviews:
        paper = paper_index[paper_id]
        for unit_index, unit in enumerate(review.get("candidate_units", []), start=1):
            label = str(unit.get("unit_label") or "").strip() if isinstance(unit, dict) else ""
            base_record = {"paper_id": paper_id, "unit_index": unit_index, "molecule_label": label}
            if not isinstance(unit, dict):
                skipped.append({**base_record, "reason": "candidate_not_object"})
                continue
            if unit.get("case_decision") not in {"make_case", "human_review"}:
                skipped.append({**base_record, "reason": f"case_decision:{unit.get('case_decision')}"})
                continue
            if unit.get("unit_type") not in {"molecule", "probe", "ligand", "guest"}:
                skipped.append({**base_record, "reason": f"non_concrete_unit_type:{unit.get('unit_type')}"})
                continue
            if not label:
                skipped.append({**base_record, "reason": "missing_unit_label"})
                continue
            target_key = (paper_id, _normalized_label(label))
            if target_key in occupied_targets:
                skipped.append({**base_record, "reason": "covered_by_explicit_or_prior_case"})
                continue
            archive_mechanism = _select_archive_mechanism(unit.get("official_mechanism_assignments"))
            if archive_mechanism is None:
                skipped.append({**base_record, "reason": "missing_valid_official_mechanism_assignment"})
                continue

            selected_images, unknown_image_ids = select_catalog_records(
                image_catalogs.get(paper_id, {"images": []}),
                unit.get("structure_image_ids") or [],
            )
            if unknown_image_ids:
                skipped.append({**base_record, "reason": f"unavailable_structure_image_ids:{','.join(unknown_image_ids)}"})
                continue
            if paper_id not in image_catalogs:
                structure_images = list(paper.get("source_images", []))
            else:
                structure_images = [str(record["path"]) for record in selected_images]

            identity_key = f"{paper.get('doi', '')}|{label}".lower()
            suffix = hashlib.sha256(identity_key.encode("utf-8")).hexdigest()[:8].upper()
            paper_slug = _identifier_part(paper_id)
            candidate_id = str(unit.get("candidate_id") or f"{paper_slug}_{unit_index:03d}_{_identifier_part(label)}")
            case_id = f"AIE_DDX_{archive_mechanism}_{paper_slug}_{suffix}"
            if case_id in occupied_ids:
                skipped.append({**base_record, "reason": f"duplicate_generated_case_id:{case_id}"})
                continue

            row = {
                "case_id": case_id,
                "candidate_id": candidate_id,
                "paper_id": paper_id,
                "molecule_label": label,
                "entity_type": unit["unit_type"],
                "structure_images": structure_images,
                "structure_image_ids": list(unit.get("structure_image_ids") or []),
                "structure_sources": list(unit.get("structure_text_sources") or unit.get("structure_source_needed") or []),
                "risk_flags": list(unit.get("stage3_risk_flags") or []),
                "source_article": {
                    "candidate_id": candidate_id,
                    "doi": str(paper["doi"]),
                    "title": str(paper.get("title") or review.get("paper_title") or ""),
                    "molecule_label": label,
                },
                "target_context": {
                    "retrieval_mechanism": str(paper["retrieval_mechanism"]),
                    "automatic_promotion": True,
                    "candidate_confidence": unit.get("confidence"),
                    "candidate_reason": unit.get("reason"),
                    "official_mechanism_assignments": unit.get("official_mechanism_assignments", []),
                },
                "archive_mechanism": archive_mechanism,
            }
            promoted.append(row)
            occupied_ids.add(case_id)
            occupied_targets.add(target_key)

    return {
        "enabled": True,
        "promotion_policy": "concrete Stage 2 make_case or human_review units with a valid official mechanism assignment; downstream structure identity review remains blocking",
        "promoted_count": len(promoted),
        "skipped_count": len(skipped),
        "promoted": promoted,
        "skipped": skipped,
    }


def _select_archive_mechanism(assignments: Any) -> str | None:
    if not isinstance(assignments, list):
        return None
    valid = [item for item in assignments if isinstance(item, dict) and item.get("mechanism") in OFFICIAL_MECHANISM_SET]
    if not valid:
        return None

    def score(item: dict[str, Any]) -> tuple[int, int]:
        role = re.sub(r"[^a-z]+", "_", str(item.get("role") or "").lower()).strip("_")
        role_score = 100 if role in {"primary", "primary_supported_mechanism"} else 90 if role in {"co_primary", "coprimary"} else 50 if role == "secondary" else 0
        evidence = str(item.get("evidence_strength") or item.get("strength") or "").lower()
        evidence_score = 20 if "strong" in evidence else 10 if "partial" in evidence or "moderate" in evidence else -20 if "unsupported" in evidence else 0
        return role_score, evidence_score

    return str(max(enumerate(valid), key=lambda pair: (*score(pair[1]), -pair[0]))[1]["mechanism"])


def _normalized_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _identifier_part(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_").upper()
    return text[:48] or "UNNAMED"


def validate_pipeline_manifest(value: dict[str, Any]) -> None:
    if not isinstance(value, dict) or value.get("manifest_version") != "1.0":
        raise ValueError("Pipeline manifest_version must be 1.0.")
    paper_ids: set[str] = set()
    for row in value.get("papers", []):
        required = {"paper_id", "doi", "retrieval_mechanism"}
        missing = required - set(row)
        if missing:
            raise ValueError(f"Paper row is missing: {sorted(missing)}")
        if bool(row.get("source_md")) == bool(row.get("source_pdf")):
            raise ValueError("Each paper row must contain exactly one of source_md or source_pdf.")
        if row["retrieval_mechanism"] not in OFFICIAL_MECHANISM_SET:
            raise ValueError(f"Unknown retrieval mechanism: {row['retrieval_mechanism']}")
        paper_ids.add(str(row["paper_id"]))
    case_ids: set[str] = set()
    for row in value.get("cases", []):
        required = {"case_id", "candidate_id", "paper_id", "molecule_label", "source_article", "archive_mechanism"}
        missing = required - set(row)
        if missing:
            raise ValueError(f"Case row is missing: {sorted(missing)}")
        if str(row["paper_id"]) not in paper_ids:
            raise ValueError(f"Case refers to unknown paper_id: {row['paper_id']}")
        if row["archive_mechanism"] not in OFFICIAL_MECHANISM_SET:
            raise ValueError(f"Unknown archive mechanism: {row['archive_mechanism']}")
        if str(row["case_id"]) in case_ids:
            raise ValueError(f"Duplicate case_id: {row['case_id']}")
        case_ids.add(str(row["case_id"]))


def _resolve(manifest_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (manifest_path.parent / path).resolve()


def _finish(output_root: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {"result_count": len(results), "failure_count": sum(row.get("status") in {"failed", "failed_gate", "not_confirmed"} for row in results), "results": results}
    _write_json(output_root / "pipeline_summary.json", summary)
    return summary


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

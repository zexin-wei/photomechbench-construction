from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from aie_ddxbench_construction.pipeline import build_automatic_case_rows, run_manifest_pipeline, validate_pipeline_manifest
from aie_ddxbench_construction.provider import ModelResponse


def test_manifest_rejects_unknown_mechanism() -> None:
    value = {"manifest_version": "1.0", "papers": [{"paper_id": "P1", "doi": "10.1/x", "source_md": "source.md", "retrieval_mechanism": "ACQ"}], "cases": []}
    with pytest.raises(ValueError, match="Unknown retrieval mechanism"):
        validate_pipeline_manifest(value)


def test_manifest_requires_case_to_reference_known_paper() -> None:
    value = {
        "manifest_version": "1.0",
        "papers": [],
        "cases": [{"case_id": "C1", "candidate_id": "X", "paper_id": "P1", "molecule_label": "A", "source_article": {}, "archive_mechanism": "RIM_RIR_RIV"}],
    }
    with pytest.raises(ValueError, match="unknown paper_id"):
        validate_pipeline_manifest(value)


def test_manifest_accepts_exactly_one_pdf_or_markdown_source() -> None:
    pdf_manifest = {
        "manifest_version": "1.0",
        "papers": [{"paper_id": "P1", "doi": "10.1/x", "source_pdf": "paper.pdf", "retrieval_mechanism": "RACI_CI_ACCESS"}],
        "cases": [],
    }
    validate_pipeline_manifest(pdf_manifest)
    pdf_manifest["papers"][0]["source_md"] = "source.md"
    with pytest.raises(ValueError, match="exactly one"):
        validate_pipeline_manifest(pdf_manifest)


def test_make_case_candidate_is_automatically_promoted() -> None:
    manifest = {
        "manifest_version": "1.0",
        "papers": [{"paper_id": "P1", "doi": "10.0000/x", "title": "Synthetic paper", "source_md": "source.md", "source_images": ["structure.png"], "retrieval_mechanism": "RACI_CI_ACCESS"}],
        "cases": [],
    }
    review = {
        "paper_title": "Synthetic paper",
        "candidate_units": [
            {
                "unit_label": "Molecule A",
                "unit_type": "molecule",
                "case_decision": "make_case",
                "confidence": "high",
                "reason": "Molecule-specific evidence is available.",
                "structure_image_ids": ["I001"],
                "structure_text_sources": ["Scheme 1"],
                "stage3_risk_flags": [],
                "official_mechanism_assignments": [
                    {"mechanism": "RIM_RIR_RIV", "role": "secondary", "evidence_strength": "moderate"},
                    {"mechanism": "RACI_CI_ACCESS", "role": "primary", "evidence_strength": "strong"},
                ],
            },
            {"unit_label": "Molecule B", "unit_type": "molecule", "case_decision": "reserve", "official_mechanism_assignments": [{"mechanism": "RACI_CI_ACCESS", "role": "primary"}]},
        ],
    }

    report = build_automatic_case_rows(
        manifest,
        [("P1", review)],
        image_catalogs={"P1": {"images": [{"image_id": "I001", "path": "structure.png"}]}},
    )

    assert report["promoted_count"] == 1
    assert report["skipped_count"] == 1
    assert report["promoted"][0]["archive_mechanism"] == "RACI_CI_ACCESS"
    assert report["promoted"][0]["structure_images"] == ["structure.png"]
    assert report["skipped"][0]["reason"] == "case_decision:reserve"


def test_explicit_case_prevents_automatic_duplicate() -> None:
    manifest = {
        "manifest_version": "1.0",
        "papers": [{"paper_id": "P1", "doi": "10.0000/x", "source_md": "source.md", "retrieval_mechanism": "RACI_CI_ACCESS"}],
        "cases": [],
    }
    existing = [{"case_id": "C1", "paper_id": "P1", "molecule_label": "Molecule-A"}]
    review = {"candidate_units": [{"unit_label": "Molecule A", "unit_type": "molecule", "case_decision": "make_case", "structure_image_ids": [], "structure_text_sources": [], "official_mechanism_assignments": [{"mechanism": "RACI_CI_ACCESS", "role": "primary"}]}]}

    report = build_automatic_case_rows(manifest, [("P1", review)], existing_cases=existing)

    assert report["promoted_count"] == 0
    assert report["skipped"][0]["reason"] == "covered_by_explicit_or_prior_case"


def test_keep_going_isolates_structure_failure(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.md"
    source.write_text("synthetic source", encoding="utf-8")
    manifest = {
        "manifest_version": "1.0",
        "papers": [{"paper_id": "P1", "doi": "10.0000/x", "source_md": "source.md", "retrieval_mechanism": "RIM_RIR_RIV"}],
        "cases": [
            {"case_id": "C1", "candidate_id": "X1", "paper_id": "P1", "molecule_label": "A", "source_article": {"candidate_id": "X1"}, "archive_mechanism": "RIM_RIR_RIV"},
            {"case_id": "C2", "candidate_id": "X2", "paper_id": "P1", "molecule_label": "B", "source_article": {"candidate_id": "X2"}, "archive_mechanism": "RIM_RIR_RIV"},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(
        "aie_ddxbench_construction.pipeline.run_paper_screen",
        lambda *args, **kwargs: SimpleNamespace(status="completed", parsed={"paper_verdict": "candidate", "recommended_image_ids": []}, error=None),
    )
    monkeypatch.setattr(
        "aie_ddxbench_construction.pipeline.run_candidate_screen",
        lambda *args, **kwargs: SimpleNamespace(status="completed", parsed={"candidate_units": []}, error=None),
    )
    calls: list[str] = []

    def fake_structure(task, **kwargs):
        calls.append(task.candidate_id)
        if task.candidate_id == "X1":
            raise RuntimeError("synthetic API failure")
        return SimpleNamespace(status="confirmed", error=None)

    monkeypatch.setattr("aie_ddxbench_construction.pipeline.run_structure_resolution", fake_structure)

    summary = run_manifest_pipeline(
        manifest_path,
        output_root=tmp_path / "out",
        client=SimpleNamespace(),
        keep_going=True,
        stop_after="structure",
    )

    assert calls == ["X1", "X2"]
    assert summary["failure_count"] == 1


def test_pipeline_routes_caption_recommendation_through_visual_selection(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("![](images/structure.png)\n\nFig. 1. Molecular structure of A.", encoding="utf-8")
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    structure_image = image_dir / "structure.png"
    Image.new("RGB", (80, 80), "white").save(structure_image)
    manifest = {
        "manifest_version": "1.0",
        "papers": [
            {
                "paper_id": "P1",
                "doi": "10.0000/x",
                "source_md": "source.md",
                "source_image_dir": "images",
                "retrieval_mechanism": "RACI_CI_ACCESS",
            }
        ],
        "cases": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class SequentialClient:
        provider_name = "fixture"
        model = "fixture"

        def __init__(self) -> None:
            self.image_calls: list[tuple[Path, ...]] = []

        def complete(self, *, system_prompt: str, user_text: str, image_paths=()):
            self.image_calls.append(tuple(image_paths))
            if len(self.image_calls) == 1:
                return ModelResponse(
                    '{"paper_verdict":"candidate","reject_reason_type":"not_rejected",'
                    '"candidate_units":[],"recommended_image_ids":["I001"]}'
                )
            return ModelResponse(
                '{"paper_title":"Synthetic","target_discovery_mechanism":"RACI_CI_ACCESS",'
                '"candidate_units":[{"unit_label":"A","unit_type":"molecule",'
                '"case_decision":"make_case","stage3_risk_flags":[],"structure_image_ids":["I001"],'
                '"structure_text_sources":["Fig. 1"],"official_mechanism_assignments":'
                '[{"mechanism":"RACI_CI_ACCESS","role":"primary","evidence_strength":"strong"}],'
                '"confidence":"high","reason":"The displayed structure is labeled A."}]}'
            )

    client = SequentialClient()
    run_manifest_pipeline(
        manifest_path,
        output_root=tmp_path / "out",
        client=client,
        stop_after="candidate_screen",
    )

    automatic = json.loads((tmp_path / "out" / "automatic_case_manifest.json").read_text(encoding="utf-8"))
    assert client.image_calls[0] == ()
    assert len(client.image_calls[1]) == 1
    assert automatic["promoted"][0]["structure_image_ids"] == ["I001"]
    assert Path(automatic["promoted"][0]["structure_images"][0]) == structure_image.resolve()


def test_pipeline_can_start_from_pdf_through_mineru_vlm(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"synthetic-pdf")
    manifest = {
        "manifest_version": "1.0",
        "papers": [
            {
                "paper_id": "P1",
                "doi": "10.0000/x",
                "source_pdf": "paper.pdf",
                "retrieval_mechanism": "RACI_CI_ACCESS",
            }
        ],
        "cases": [],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    parse_calls: list[Path] = []

    def fake_parse(path: Path, *, output_dir: Path, **kwargs):
        parse_calls.append(path)
        output_dir.mkdir(parents=True)
        source = output_dir / "source.md"
        source.write_text("Synthetic parsed paper.", encoding="utf-8")
        images = output_dir / "images"
        images.mkdir()
        return {"source_markdown": str(source), "source_image_dir": str(images)}

    monkeypatch.setattr("aie_ddxbench_construction.pipeline.parse_pdf_with_mineru_vlm", fake_parse)
    monkeypatch.setattr(
        "aie_ddxbench_construction.pipeline.run_paper_screen",
        lambda *args, **kwargs: SimpleNamespace(
            status="completed",
            parsed={"paper_verdict": "reject", "recommended_image_ids": []},
            error=None,
        ),
    )

    summary = run_manifest_pipeline(
        manifest_path,
        output_root=tmp_path / "out",
        client=SimpleNamespace(),
        stop_after="paper_screen",
        mineru_options={"token": "secret"},
    )

    assert parse_calls == [pdf.resolve()]
    assert [row["stage"] for row in summary["results"]] == ["mineru_vlm", "paper_screen"]

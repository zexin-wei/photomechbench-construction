from __future__ import annotations

import json
from pathlib import Path

from aie_ddxbench_construction.provider import ModelResponse
from aie_ddxbench_construction.screening import (
    ParsedPaper,
    build_candidate_screen_prompt,
    build_paper_screen_prompt,
    candidate_manifest_rows,
    run_paper_screen,
    validate_candidate_review,
)


class FixtureClient:
    provider_name = "fixture"
    model = "fixture-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def complete(self, *, system_prompt: str, user_text: str, image_paths=()):
        self.calls += 1
        return ModelResponse(self.text)


def _paper(tmp_path: Path) -> ParsedPaper:
    source = tmp_path / "source.md"
    source.write_text("# Paper\nMolecule A shows aggregation-dependent emission.", encoding="utf-8")
    return ParsedPaper("10.1000/example", source, "Example", "example.pdf")


def test_screening_prompts_keep_retrieval_mechanism_as_hypothesis(tmp_path: Path) -> None:
    paper = _paper(tmp_path)
    stage1 = build_paper_screen_prompt(paper, retrieval_mechanism="RACI_CI_ACCESS")
    stage2 = build_candidate_screen_prompt(
        paper,
        retrieval_mechanism="RACI_CI_ACCESS",
        paper_review={"paper_verdict": "candidate"},
    )
    assert "only a search hypothesis" in stage1
    assert "Do not generate benchmark JSON or SMILES" in stage1
    assert "stage2_evidence_requests" not in stage1
    assert "remains a hypothesis, not a final label" in stage2
    assert "Do not invent or finalize SMILES" in stage2
    for unused_field in (
        "supporting_context_units",
        "stage3_requests",
        "global_concerns",
        "next_step_summary",
        "target_mechanism_verdict",
        "evidence_sufficiency",
        "smiles_status",
        "stage3_expected_route",
        "positive_evidence_summary",
        "negative_evidence_summary",
    ):
        assert unused_field not in stage2


def test_candidate_validation_rejects_nonofficial_mechanism() -> None:
    review = {
        "candidate_units": [
            {
                "unit_type": "molecule",
                "case_decision": "make_case",
                "official_mechanism_assignments": [{"mechanism": "ACQ"}],
            }
        ]
    }
    assert any("non-official" in error for error in validate_candidate_review(review))


def test_manifest_keeps_only_concrete_case_candidates() -> None:
    review = {
        "doi": "10.1000/x",
        "target_discovery_mechanism": "RIM_RIR_RIV",
        "candidate_units": [
            {"unit_label": "A", "unit_type": "molecule", "case_decision": "make_case"},
            {"unit_label": "Series", "unit_type": "unclear", "case_decision": "make_case"},
            {"unit_label": "Control", "unit_type": "molecule", "case_decision": "supporting_control"},
        ],
    }
    rows = candidate_manifest_rows([review])
    assert [row["molecule_label"] for row in rows] == ["A"]
    assert "doi" not in rows[0]
    assert "smiles_status" not in rows[0]
    assert "stage3_expected_route" not in rows[0]


def test_resume_skips_only_hash_valid_success(tmp_path: Path) -> None:
    paper = _paper(tmp_path)
    response = """{
      "doi": "10.1000/example",
      "title": "Example",
      "paper_verdict": "candidate",
      "reject_reason_type": "not_rejected",
      "recommended_image_ids": [],
      "candidate_units": []
    }"""
    client = FixtureClient(response)
    output = tmp_path / "screen"
    first = run_paper_screen(paper, retrieval_mechanism="RACI_CI_ACCESS", output_dir=output, client=client)
    second = run_paper_screen(paper, retrieval_mechanism="RACI_CI_ACCESS", output_dir=output, client=client, resume=True)
    assert first.status == "completed"
    assert second.status == "skipped_valid"
    assert client.calls == 1


def test_failed_screen_is_not_resume_success(tmp_path: Path) -> None:
    paper = _paper(tmp_path)
    client = FixtureClient("not json")
    output = tmp_path / "screen"
    first = run_paper_screen(paper, retrieval_mechanism="RACI_CI_ACCESS", output_dir=output, client=client)
    second = run_paper_screen(paper, retrieval_mechanism="RACI_CI_ACCESS", output_dir=output, client=client, resume=True)
    assert first.status == "failed"
    assert second.status == "failed"
    assert client.calls == 2


def test_resume_retries_when_prompt_hash_is_stale(tmp_path: Path) -> None:
    paper = _paper(tmp_path)
    response = """{
      "doi": "10.1000/example",
      "title": "Example",
      "paper_verdict": "candidate",
      "reject_reason_type": "not_rejected",
      "recommended_image_ids": [],
      "candidate_units": []
    }"""
    client = FixtureClient(response)
    output = tmp_path / "screen"
    first = run_paper_screen(paper, retrieval_mechanism="RACI_CI_ACCESS", output_dir=output, client=client)
    request_path = output / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["prompt_sha256"] = "stale"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    second = run_paper_screen(paper, retrieval_mechanism="RACI_CI_ACCESS", output_dir=output, client=client, resume=True)

    assert first.status == "completed"
    assert second.status == "completed"
    assert client.calls == 2

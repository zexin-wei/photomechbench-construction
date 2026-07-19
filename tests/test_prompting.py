from __future__ import annotations

import re

from aie_ddxbench_construction.prompting import (
    INDEPENDENT_REVIEW_SYSTEM_PROMPT,
    build_independent_review_text,
    load_prompt,
)


def test_independent_review_prompt_is_packaged() -> None:
    prompt = load_prompt("independent_review_v1")
    assert "PASS_WITH_CAVEAT" in prompt
    assert "NEEDS_MINOR_FIX" in prompt
    assert "FAIL_OR_REBUILD" in prompt


def test_all_model_stages_have_versioned_prompt_assets() -> None:
    names = (
        "paper_screen_v1",
        "candidate_screen_v1",
        "smiles_proposal_v1",
        "structure_identity_review_v1",
        "smiles_repair_v1",
        "reference_construction_v1",
        "reference_gate_repair_v1",
        "independent_review_v1",
        "minor_repair_v1",
        "gate_repair_v1",
    )
    for name in names:
        assert load_prompt(name).strip(), name


def test_review_request_has_three_artifact_boundary_and_no_machine_path() -> None:
    request = build_independent_review_text(
        case_name="AIE_DDX_EXAMPLE_001",
        archive_mechanism="RIM_RIR_RIV",
        case_json_text="{}",
        source_text="Synthetic source.",
        include_image=True,
    )
    assert "final_reference_alignment.json" in request
    assert "source.md" in request
    assert "structure_match.png" in request
    assert "Do not browse" in request
    assert "C:\\" not in request
    assert "hidden reasoning" in INDEPENDENT_REVIEW_SYSTEM_PROMPT


def test_review_prompt_text_has_no_encoding_damage() -> None:
    request = build_independent_review_text(
        case_name="AIE_DDX_EXAMPLE_001",
        archive_mechanism="RIM_RIR_RIV",
        case_json_text="{}",
        source_text="Synthetic source.",
        include_image=True,
    )
    combined = INDEPENDENT_REVIEW_SYSTEM_PROMPT + request
    assert "strict reviewer" in combined
    assert "Use only final_reference_alignment.json" in combined
    assert "visual structure check" in combined
    assert "\ufffd" not in combined


def test_all_versioned_prompts_are_english_only() -> None:
    names = (
        "paper_screen_v1",
        "candidate_screen_v1",
        "smiles_proposal_v1",
        "structure_identity_review_v1",
        "smiles_repair_v1",
        "reference_construction_v1",
        "reference_gate_repair_v1",
        "independent_review_v1",
        "minor_repair_v1",
        "gate_repair_v1",
    )
    cjk = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    for name in names:
        assert not cjk.search(load_prompt(name)), name
    assert not cjk.search(INDEPENDENT_REVIEW_SYSTEM_PROMPT)

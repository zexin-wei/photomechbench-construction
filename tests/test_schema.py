from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from aie_ddxbench_construction.schema import validate_raw_case


FIXTURE = Path(__file__).parent / "fixtures" / "valid_case.json"


def load_case() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def issue_codes(case: dict) -> set[str]:
    return {issue.code for issue in validate_raw_case(case)}


def test_valid_case_passes() -> None:
    assert validate_raw_case(load_case()) == []


def test_unknown_evidence_link_fails() -> None:
    case = load_case()
    case["hidden_reference"]["reference_diagnosis_units"][0]["supporting_evidence_ids"] = ["E99"]
    assert "unknown_supporting_evidence_id" in issue_codes(case)


def test_final_synthesis_is_required_exactly_once() -> None:
    case = load_case()
    case["hidden_reference"]["reference_diagnosis_units"] = case["hidden_reference"]["reference_diagnosis_units"][:1]
    assert "final_synthesis_count" in issue_codes(case)


def test_underdetermined_diagnosis_keeps_scope_evidence() -> None:
    case = load_case()
    diagnosis = case["hidden_reference"]["reference_diagnosis_units"][0]
    assert diagnosis["reference_status"] == "underdetermined"
    assert diagnosis["supporting_evidence_ids"] == ["E01"]
    assert validate_raw_case(case) == []


def test_public_input_rejects_extra_answer_field() -> None:
    case = deepcopy(load_case())
    case["public_input"]["target_mechanism"] = "RIM_RIR_RIV"
    assert "json_schema" in issue_codes(case)

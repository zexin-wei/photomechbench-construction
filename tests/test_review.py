from __future__ import annotations

import shutil
from pathlib import Path

from aie_ddxbench_construction.provider import ModelResponse
from aie_ddxbench_construction.review import ReviewCase, parse_review_decision, run_independent_review


FIXTURE = Path(__file__).parent / "fixtures" / "valid_case.json"


class FakeClient:
    provider_name = "test-provider"
    model = "test-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def complete(self, *, system_prompt: str, user_text: str, image_paths=()) -> ModelResponse:
        self.calls += 1
        assert len(image_paths) == 1
        return ModelResponse(self.text, response_id="response-1", response_model=self.model, usage={"total_tokens": 10})


def make_case(tmp_path: Path) -> ReviewCase:
    case_dir = tmp_path / "RIM_RIR_RIV" / "AIE_DDX_EXAMPLE_001"
    case_dir.mkdir(parents=True)
    shutil.copy2(FIXTURE, case_dir / "final_reference_alignment.json")
    (case_dir / "source.md").write_text("Synthetic source.", encoding="utf-8")
    (case_dir / "structure_match.png").write_bytes(b"synthetic-png-fixture")
    return ReviewCase.from_directory(case_dir)


def test_parse_review_decision() -> None:
    assert parse_review_decision("overall_decision:\nPASS_WITH_CAVEAT") == "PASS_WITH_CAVEAT"
    assert parse_review_decision("overall_decision: INVALID") is None


def test_review_resume_skips_only_verified_success(tmp_path) -> None:
    client = FakeClient("overall_decision:\nPASS\n")
    case = make_case(tmp_path)
    out = tmp_path / "review"
    first = run_independent_review(case, output_dir=out, client=client)
    second = run_independent_review(case, output_dir=out, client=client, resume=True)
    assert first.status == "completed"
    assert second.status == "skipped_valid"
    assert client.calls == 1


def test_invalid_review_is_recorded_as_failure_and_retried(tmp_path) -> None:
    client = FakeClient("No structured decision.")
    case = make_case(tmp_path)
    out = tmp_path / "review"
    first = run_independent_review(case, output_dir=out, client=client)
    second = run_independent_review(case, output_dir=out, client=client, resume=True)
    assert first.status == "failed"
    assert second.status == "failed"
    assert client.calls == 2

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from aie_ddxbench_construction.provider import ModelResponse
from aie_ddxbench_construction.repair import run_minor_repair


FIXTURE = Path(__file__).parent / "fixtures" / "valid_case.json"
QUOTE = "The synthetic source reports an environment-dependent emission change."


class RepairClient:
    provider_name = "test-provider"
    model = "test-model"

    def __init__(self, revised: dict) -> None:
        self.revised = revised

    def complete(self, *, system_prompt: str, user_text: str, image_paths=()) -> ModelResponse:
        return ModelResponse(json.dumps({"revised_json": self.revised, "changes": []}))


def inputs(tmp_path: Path, decision: str = "NEEDS_MINOR_FIX") -> dict[str, Path]:
    root = tmp_path / "input"
    root.mkdir()
    original = root / "final_reference_alignment.json"
    shutil.copy2(FIXTURE, original)
    source = root / "source.md"
    source.write_text(QUOTE, encoding="utf-8")
    image = root / "structure_match.png"
    image.write_bytes(b"synthetic-image")
    review = root / "review.md"
    review.write_text(f"overall_decision:\n{decision}\n", encoding="utf-8")
    return {"original": original, "source": source, "image": image, "review": review}


def test_minor_repair_packages_gate_clean_case(tmp_path) -> None:
    paths = inputs(tmp_path)
    original = json.loads(paths["original"].read_text(encoding="utf-8"))
    client = RepairClient(original)
    result = run_minor_repair(
        original_case_path=paths["original"],
        source_path=paths["source"],
        structure_match_path=paths["image"],
        review_path=paths["review"],
        locked_structure={"locked_smiles": "CCO", "final_structure_status": "validated"},
        output_dir=tmp_path / "repair",
        client=client,
    )
    assert result.packaged_for_rereview
    assert (tmp_path / "repair" / "rereview_input" / "final_reference_alignment.json").is_file()


def test_protected_public_input_change_blocks_packaging(tmp_path) -> None:
    paths = inputs(tmp_path)
    revised = json.loads(paths["original"].read_text(encoding="utf-8"))
    revised["public_input"]["molecule"]["structure"]["value"] = "CCN"
    result = run_minor_repair(
        original_case_path=paths["original"],
        source_path=paths["source"],
        structure_match_path=paths["image"],
        review_path=paths["review"],
        locked_structure={"locked_smiles": "CCO", "final_structure_status": "validated"},
        output_dir=tmp_path / "repair",
        client=RepairClient(revised),
    )
    assert not result.packaged_for_rereview
    assert "protected_field_changed:public_input" in result.validation_errors


def test_forbidden_internal_root_field_is_removed(tmp_path) -> None:
    paths = inputs(tmp_path)
    revised = json.loads(paths["original"].read_text(encoding="utf-8"))
    revised["structure_resolution_report"] = {"internal": True}
    result = run_minor_repair(
        original_case_path=paths["original"],
        source_path=paths["source"],
        structure_match_path=paths["image"],
        review_path=paths["review"],
        locked_structure={"locked_smiles": "CCO", "final_structure_status": "validated"},
        output_dir=tmp_path / "repair",
        client=RepairClient(revised),
    )
    packaged = json.loads(
        (tmp_path / "repair" / "rereview_input" / "final_reference_alignment.json").read_text(encoding="utf-8")
    )
    assert result.packaged_for_rereview
    assert "structure_resolution_report" not in packaged


def test_only_needs_minor_fix_can_enter_repair(tmp_path) -> None:
    paths = inputs(tmp_path, decision="PASS")
    original = json.loads(paths["original"].read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="NEEDS_MINOR_FIX"):
        run_minor_repair(
            original_case_path=paths["original"],
            source_path=paths["source"],
            structure_match_path=paths["image"],
            review_path=paths["review"],
            locked_structure={"locked_smiles": "CCO", "final_structure_status": "validated"},
            output_dir=tmp_path / "repair",
            client=RepairClient(original),
        )

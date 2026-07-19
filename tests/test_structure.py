from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from aie_ddxbench_construction.provider import ModelResponse
from aie_ddxbench_construction.structure import StructureTask, run_structure_resolution


class SequenceClient:
    provider_name = "fixture"
    model = "fixture-model"

    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(self, *, system_prompt: str, user_text: str, image_paths=()):
        self.calls += 1
        return ModelResponse(json.dumps(self.responses.pop(0)))


def _task(tmp_path: Path) -> StructureTask:
    source = tmp_path / "source.md"
    source.write_text("# Example\nCompound A is ethanol in this fixture.", encoding="utf-8")
    image = tmp_path / "scheme.png"
    Image.new("RGB", (500, 300), "white").save(image)
    return StructureTask("C001", "10.1000/x", "A", "molecule", source, (image,), "Example")


def test_structure_lock_requires_rdkit_and_confirmed_identity(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AIE_DDX_RDKIT_CONDA_ENV", "molscribe_py310")
    client = SequenceClient(
        [
            {"proposed_smiles": "CCO", "final_decision": "proceed_to_rdkit"},
            {
                "candidate_smiles": "WRITTEN-BY-MODEL",
                "structure_match_status": "confirmed_match",
                "single_molecule_ok": True,
                "target_label_ok": True,
                "not_confused_with_other_paper_molecule": True,
                "final_stage3_decision": "confirmed_smiles",
                "recommended_next_action": "proceed",
            },
        ]
    )
    output = tmp_path / "out"
    result = run_structure_resolution(_task(tmp_path), output_dir=output, client=client)
    assert result.status == "confirmed"
    assert result.locked_smiles == "CCO"
    lock = json.loads((output / "locked_structure.json").read_text(encoding="utf-8"))
    assert lock["locked_smiles"] == "CCO"
    assert "final_selected_smiles" not in lock
    assert "locked_selected_smiles" not in lock
    assert lock["identity_review"]["candidate_smiles"] == "CCO"
    assert (output / "structure_match.png").is_file()


def test_probable_identity_does_not_create_lock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AIE_DDX_RDKIT_CONDA_ENV", "molscribe_py310")
    review = {
        "structure_match_status": "probable_match",
        "single_molecule_ok": True,
        "target_label_ok": True,
        "not_confused_with_other_paper_molecule": True,
        "final_stage3_decision": "probable_smiles",
        "recommended_next_action": "human check",
    }
    client = SequenceClient(
        [
            {"proposed_smiles": "CCO", "final_decision": "proceed_to_rdkit"},
            review,
            {"proposed_smiles": None, "repair_action": "cannot_fix"},
        ]
    )
    output = tmp_path / "out"
    result = run_structure_resolution(_task(tmp_path), output_dir=output, client=client)
    assert result.status == "not_confirmed"
    assert not (output / "locked_structure.json").exists()

from __future__ import annotations

from pathlib import Path

from aie_ddxbench_construction.public_input import CANONICAL_SMILES_ONLY_TASK
from aie_ddxbench_construction.reference import ReferenceTask, build_reference_prompt


def test_reference_prompt_locks_target_and_explains_hidden_reference(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("Paper source", encoding="utf-8")
    lock = tmp_path / "locked_structure.json"
    lock.write_text("{}", encoding="utf-8")
    match = tmp_path / "structure_match.png"
    match.write_bytes(b"png")
    task = ReferenceTask(
        "AIE_DDX_TEST_001",
        source,
        lock,
        match,
        {"candidate_id": "C001", "doi": "10.1000/x", "title": "Example", "molecule_label": "A"},
    )
    prompt = build_reference_prompt(task, source="Paper source", locked_smiles="CCO")
    assert "Do not select another molecule" in prompt
    assert CANONICAL_SMILES_ONLY_TASK in prompt
    assert "reference evidence unit" in prompt
    assert "reference diagnosis unit" in prompt
    assert "not a twelfth mechanism family" in prompt
    assert "underdetermined" in prompt

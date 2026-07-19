from __future__ import annotations

import json
import shutil
from pathlib import Path

from aie_ddxbench_construction.dataset import ReleaseCase, audit_release_cases, package_accepted_cases


FIXTURE = Path(__file__).parent / "fixtures" / "valid_case.json"


def test_pass_case_audits_and_packages_two_part_release(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "case"
    review_dir = tmp_path / "review"
    case_dir.mkdir()
    review_dir.mkdir()
    shutil.copy2(FIXTURE, case_dir / "final_reference_alignment.json")
    (case_dir / "source.md").write_text("DOI: 10.0000/example\nSynthetic source.", encoding="utf-8")
    (case_dir / "structure_match.png").write_bytes(b"synthetic-image")
    (review_dir / "review_summary.json").write_text(json.dumps({"decision": "PASS_WITH_CAVEAT"}), encoding="utf-8")
    monkeypatch.setattr(
        "aie_ddxbench_construction.dataset.structure_identity",
        lambda smiles: {
            "parse_success": True,
            "canonical_smiles": smiles,
            "structure_key": "KEY-1",
            "largest_fragment_key": "KEY-1",
            "component_count": 1,
        },
    )
    item = ReleaseCase("RIM_RIR_RIV", case_dir, review_dir)

    audit = audit_release_cases([item])
    package = package_accepted_cases([item], output_dir=tmp_path / "release")

    assert audit["passed"] is True
    assert package["case_count"] == 1
    assert (tmp_path / "release" / "submission_json_1" / "RIM_RIR_RIV" / "AIE_DDX_EXAMPLE_001.json").is_file()
    assert (tmp_path / "release" / "internal_provenance_and_reviews_1" / "stage5_reviews" / "RIM_RIR_RIV" / "AIE_DDX_EXAMPLE_001" / "review_summary.json").is_file()

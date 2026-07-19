from __future__ import annotations

import json
from pathlib import Path

from aie_ddxbench_construction.local_gate import run_local_gate


FIXTURE = Path(__file__).parent / "fixtures" / "valid_case.json"
SOURCE = "The synthetic source reports an environment-dependent emission change."


def load_case() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def structure_report(smiles: str = "CCO") -> dict:
    return {
        "locked_smiles": smiles,
        "final_structure_status": "validated",
    }


def test_complete_local_gate_passes_synthetic_fixture() -> None:
    report = run_local_gate(
        case=load_case(),
        source_markdown=SOURCE,
        locked_structure=structure_report(),
    )
    assert report["gate_passed"], report["blocking_issues"]


def test_locked_public_smiles_mismatch_blocks() -> None:
    report = run_local_gate(
        case=load_case(),
        source_markdown=SOURCE,
        locked_structure=structure_report("CCN"),
    )
    issue_types = {issue["issue_type"] for issue in report["blocking_issues"]}
    assert "public_smiles_mismatch" in issue_types


def test_missing_quote_blocks() -> None:
    report = run_local_gate(
        case=load_case(),
        source_markdown="No matching source sentence.",
        locked_structure=structure_report(),
    )
    issue_types = {issue["issue_type"] for issue in report["blocking_issues"]}
    assert "paper_quote_not_found" in issue_types

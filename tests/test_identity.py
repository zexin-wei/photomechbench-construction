from __future__ import annotations

from aie_ddxbench_construction.identity import structure_identity


def test_structure_identity_uses_configured_rdkit(monkeypatch) -> None:
    monkeypatch.setenv("AIE_DDX_RDKIT_CONDA_ENV", "molscribe_py310")
    report = structure_identity("CCO")
    assert report["parse_success"] is True
    assert report["canonical_smiles"] == "CCO"
    assert report["inchi_key"]
    assert report["component_count"] == 1

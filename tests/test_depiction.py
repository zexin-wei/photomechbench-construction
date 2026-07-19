from __future__ import annotations

from pathlib import Path

from PIL import Image

from aie_ddxbench_construction.depiction import render_smiles


def test_render_smiles_uses_configured_rdkit_runtime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AIE_DDX_RDKIT_CONDA_ENV", "molscribe_py310")
    output = tmp_path / "ethanol.png"
    report = render_smiles("CCO", output, size=(320, 240))
    assert report["success"] is True
    assert output.is_file()
    with Image.open(output) as image:
        assert image.size == (320, 240)

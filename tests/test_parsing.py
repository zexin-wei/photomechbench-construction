from __future__ import annotations

import json
from pathlib import Path

from aie_ddxbench_construction.parsing import import_mineru_export


def test_import_mineru_export_selects_largest_markdown_and_hashes_images(tmp_path: Path) -> None:
    export = tmp_path / "mineru"
    export.mkdir()
    (export / "small.md").write_text("short", encoding="utf-8")
    (export / "full.md").write_text("full parsed paper\n" * 20, encoding="utf-8")
    (export / "figure.png").write_bytes(b"synthetic-image")

    report = import_mineru_export(export, output_dir=tmp_path / "parsed")

    assert Path(report["source_markdown"]).read_text(encoding="utf-8").startswith("full parsed paper")
    assert report["images"][0]["sha256"]
    saved = json.loads((tmp_path / "parsed" / "parser_report.json").read_text(encoding="utf-8"))
    assert saved["parser"] == "MinerU"

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from aie_ddxbench_construction.mineru_api import parse_pdf_with_mineru_vlm


def test_mineru_vlm_adapter_saves_raw_and_canonical_outputs(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"synthetic-pdf")
    calls: list[dict] = []

    class FakeResult:
        state = "done"
        task_id = "task-123"

        def save_all(self, output_dir: str) -> None:
            root = Path(output_dir)
            root.mkdir(parents=True)
            (root / "full.md").write_text("![](figure.png)\n\nFig. 1. Molecular structure.", encoding="utf-8")
            Image.new("RGB", (20, 20), "white").save(root / "figure.png")

    class FakeMinerU:
        def __init__(self, **kwargs) -> None:
            calls.append({"client": kwargs})

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def extract(self, path: str, **kwargs):
            calls.append({"path": path, "extract": kwargs})
            return FakeResult()

    monkeypatch.setattr("aie_ddxbench_construction.mineru_api._load_sdk", lambda: FakeMinerU)
    output = tmp_path / "parsed"
    report = parse_pdf_with_mineru_vlm(pdf, output_dir=output, token="secret", language="en")

    assert report["success"] is True
    assert report["task_id"] == "task-123"
    assert report["image_count"] == 1
    assert (output / "source.md").is_file()
    assert (output / "images" / "figure.png").is_file()
    assert calls[1]["extract"]["model"] == "vlm"
    serialized = (output / "mineru_api_request.json").read_text(encoding="utf-8")
    assert "secret" not in serialized

    cached = parse_pdf_with_mineru_vlm(pdf, output_dir=output, token="secret", language="en", resume=True)
    assert cached["task_id"] == "task-123"
    assert len(calls) == 2


def test_mineru_failure_report_does_not_record_token(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"synthetic-pdf")

    class FailingMinerU:
        def __init__(self, **kwargs) -> None:
            raise RuntimeError(f"synthetic failure for {kwargs['token']}")

    monkeypatch.setattr("aie_ddxbench_construction.mineru_api._load_sdk", lambda: FailingMinerU)
    output = tmp_path / "parsed"
    try:
        parse_pdf_with_mineru_vlm(pdf, output_dir=output, token="do-not-write")
    except RuntimeError:
        pass

    report = json.loads((output / "mineru_api_report.json").read_text(encoding="utf-8"))
    assert report["success"] is False
    assert "do-not-write" not in json.dumps(report)

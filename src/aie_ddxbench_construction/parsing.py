"""Import a MinerU client export into the canonical parsed-paper contract."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .image_catalog import build_image_catalog


def import_mineru_export(export_dir: Path, *, output_dir: Path) -> dict[str, Any]:
    """Copy the best Markdown and related images without depending on batch paths."""
    markdown_files = sorted(export_dir.rglob("*.md"), key=lambda path: path.stat().st_size, reverse=True)
    if not markdown_files:
        raise FileNotFoundError(f"No Markdown file found in MinerU export: {export_dir}")
    source = markdown_files[0]
    output_dir.mkdir(parents=True, exist_ok=True)
    canonical_source = output_dir / "source.md"
    shutil.copy2(source, canonical_source)
    image_root = output_dir / "images"
    image_rows: list[dict[str, Any]] = []
    for index, image in enumerate(sorted(path for path in export_dir.rglob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}), start=1):
        destination = image_root / image.name
        if destination.exists():
            destination = image_root / f"{index:04d}_{image.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, destination)
        image_rows.append({"path": str(destination), "source_name": image.name, "sha256": _sha256(destination)})
    catalog = build_image_catalog(canonical_source, [Path(row["path"]) for row in image_rows])
    catalog_ids = {str(row["path"]): row["image_id"] for row in catalog["images"]}
    for row in image_rows:
        row["image_id"] = catalog_ids[str(Path(row["path"]).resolve())]
    (output_dir / "image_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "parser": "MinerU",
        "import_mode": "existing_client_export",
        "source_markdown": str(canonical_source),
        "source_markdown_sha256": _sha256(canonical_source),
        "source_markdown_bytes": canonical_source.stat().st_size,
        "images": image_rows,
        "image_catalog": str(output_dir / "image_catalog.json"),
    }
    (output_dir / "parser_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return digest.hexdigest()

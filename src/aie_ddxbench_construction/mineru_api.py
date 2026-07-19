"""MinerU VLM cloud API adapter for PDF-to-canonical-paper parsing."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .parsing import import_mineru_export


def parse_pdf_with_mineru_vlm(
    pdf_path: Path,
    *,
    output_dir: Path,
    token: str,
    base_url: str | None = None,
    language: str = "en",
    pages: str | None = None,
    ocr: bool = False,
    formula: bool = True,
    table: bool = True,
    timeout: float = 1800.0,
    resume: bool = False,
) -> dict[str, Any]:
    """Parse one local PDF with MinerU Precision Extract using the VLM model."""
    pdf_path = pdf_path.resolve()
    output_dir = output_dir.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")
    if not token:
        raise ValueError("A non-empty MinerU API token is required.")

    options = {
        "model": "vlm",
        "language": language,
        "pages": pages,
        "ocr": ocr,
        "formula": formula,
        "table": table,
        "timeout": timeout,
        "base_url": base_url,
    }
    pdf_hash = _sha256(pdf_path)
    report_path = output_dir / "mineru_api_report.json"
    if resume:
        cached = _load_valid_report(report_path, pdf_hash=pdf_hash, options=options)
        if cached is not None:
            return cached
    if (output_dir / "source.md").exists():
        raise FileExistsError(
            f"Canonical MinerU output already exists: {output_dir / 'source.md'}. "
            "Use --resume for a matching completed parse or choose a new output directory."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / f"api_export_{uuid.uuid4().hex[:12]}"
    request_record = {
        "adapter": "mineru_open_sdk",
        "api_mode": "precision_extract",
        "input_pdf": str(pdf_path),
        "input_pdf_sha256": pdf_hash,
        "options": options,
        "token_recorded": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output_dir / "mineru_api_request.json", request_record)

    try:
        MinerU = _load_sdk()
        client_options: dict[str, Any] = {"token": token}
        if base_url:
            client_options["base_url"] = base_url
        extract_options = {
            "model": "vlm",
            "language": language,
            "ocr": ocr,
            "formula": formula,
            "table": table,
            "timeout": timeout,
        }
        if pages:
            extract_options["pages"] = pages
        with MinerU(**client_options) as client:
            result = client.extract(str(pdf_path), **extract_options)
            result.save_all(str(raw_dir))
        import_report = import_mineru_export(raw_dir, output_dir=output_dir)
        report = {
            **request_record,
            "success": True,
            "state": getattr(result, "state", None),
            "task_id": getattr(result, "task_id", None),
            "raw_export_dir": str(raw_dir),
            "source_markdown": import_report["source_markdown"],
            "source_image_dir": str(output_dir / "images"),
            "image_count": len(import_report["images"]),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(report_path, report)
        return report
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}".replace(token, "<redacted>")
        report = {
            **request_record,
            "success": False,
            "raw_export_dir": str(raw_dir),
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(report_path, report)
        raise


def _load_sdk() -> Any:
    try:
        version("mineru-open-sdk")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "MinerU Open API support is not installed. Install the project with "
            "`python -m pip install -e .` or install `mineru-open-sdk`."
        ) from exc
    try:
        from mineru import MinerU
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(
            "The installed `mineru` module does not expose the MinerU Open API SDK. "
            "Use the dedicated aie-ddxbench-construction environment and reinstall "
            "`mineru-open-sdk`."
        ) from exc
    return MinerU


def _load_valid_report(path: Path, *, pdf_hash: str, options: dict[str, Any]) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    source = Path(str(report.get("source_markdown") or ""))
    if (
        report.get("success") is True
        and report.get("input_pdf_sha256") == pdf_hash
        and report.get("options") == options
        and source.is_file()
    ):
        return report
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

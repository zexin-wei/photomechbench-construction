"""Command-line entry point for the canonical release package."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .dataset import ReleaseCase, audit_release_cases, package_accepted_cases
from .literature import TavilyRestClient, run_literature_retrieval, verify_pdf_identity
from .mineru_api import parse_pdf_with_mineru_vlm
from .parsing import import_mineru_export
from .pipeline import run_manifest_pipeline
from .provider import OpenAICompatibleClient
from .review import ReviewCase, run_review_batch
from .schema import validate_json_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aie-ddxbench")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit-json", help="Validate v0.4 case JSON files without API access.")
    audit.add_argument("--case-root", type=Path, required=True)
    audit.add_argument("--out", type=Path, required=True)

    retrieve = sub.add_parser("retrieve-literature", help="Run and persist mechanism-oriented Tavily literature retrieval.")
    retrieve.add_argument("--mechanism", required=True)
    retrieve.add_argument("--out-dir", type=Path, required=True)
    retrieve.add_argument("--api-key-env", default="TAVILY_API_KEY")
    retrieve.add_argument("--base-url", default="https://api.tavily.com")
    retrieve.add_argument("--max-results", type=int, default=20)
    retrieve.add_argument("--max-queries", type=int, default=None)
    retrieve.add_argument("--search-depth", choices=["basic", "advanced", "fast", "ultra-fast"], default="advanced")
    retrieve.add_argument("--skip-crossref", action="store_true", help="Do not use Crossref title matching for hits without a visible DOI.")
    retrieve.add_argument("--timeout", type=float, default=60.0)

    pdf = sub.add_parser("verify-pdf", help="Check a local PDF against expected DOI/title.")
    pdf.add_argument("--pdf", type=Path, required=True)
    pdf.add_argument("--doi", required=True)
    pdf.add_argument("--title", default="")
    pdf.add_argument("--out", type=Path, required=True)

    mineru = sub.add_parser("import-mineru", help="Import an existing MinerU client export.")
    mineru.add_argument("--export-dir", type=Path, required=True)
    mineru.add_argument("--out-dir", type=Path, required=True)

    mineru_vlm = sub.add_parser("parse-mineru-vlm", help="Parse a local PDF with the MinerU Precision Extract VLM API.")
    mineru_vlm.add_argument("--pdf", type=Path, required=True)
    mineru_vlm.add_argument("--out-dir", type=Path, required=True)
    mineru_vlm.add_argument("--token-env", default="MINERU_API_TOKEN")
    mineru_vlm.add_argument("--base-url", default=None)
    mineru_vlm.add_argument("--language", default="en")
    mineru_vlm.add_argument("--pages", default=None)
    mineru_vlm.add_argument("--ocr", action="store_true")
    mineru_vlm.add_argument("--no-formula", action="store_true")
    mineru_vlm.add_argument("--no-table", action="store_true")
    mineru_vlm.add_argument("--timeout", type=float, default=1800.0)
    mineru_vlm.add_argument("--resume", action="store_true")

    pipeline = sub.add_parser("run-pipeline", help="Run the manifest-driven construction pipeline.")
    pipeline.add_argument("--manifest", type=Path, required=True)
    pipeline.add_argument("--out-root", type=Path, required=True)
    pipeline.add_argument("--stop-after", choices=["paper_screen", "candidate_screen", "structure", "reference", "review"], default="review")
    pipeline.add_argument("--resume", action="store_true")
    pipeline.add_argument("--keep-going", action="store_true")
    _mineru_pipeline_args(pipeline)
    _model_args(pipeline)

    review = sub.add_parser("review-cases", help="Run independent English review for explicit three-artifact case directories.")
    review.add_argument("--case-dir", type=Path, action="append", required=True, help="Repeat for each directory containing final_reference_alignment.json, source.md, and structure_match.png.")
    review.add_argument("--out-root", type=Path, required=True)
    review.add_argument("--resume", action="store_true")
    review.add_argument("--keep-going", action="store_true")
    _model_args(review)

    dataset_audit = sub.add_parser("audit-release", help="Audit review-accepted release cases and duplicates.")
    dataset_audit.add_argument("--manifest", type=Path, required=True, help="JSON release manifest with archive_mechanism, case_dir, and review_dir rows.")
    dataset_audit.add_argument("--out", type=Path, required=True)

    package = sub.add_parser("package-release", help="Package accepted cases after deterministic release audit.")
    package.add_argument("--manifest", type=Path, required=True)
    package.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "audit-json":
        return audit_json(args.case_root, args.out)
    if args.command == "retrieve-literature":
        key = os.environ.get(args.api_key_env)
        if not key:
            raise ValueError(f"API key environment variable is not set: {args.api_key_env}")
        client = TavilyRestClient(key, base_url=args.base_url, timeout=args.timeout)
        summary = run_literature_retrieval(
            args.mechanism,
            client=client,
            output_dir=args.out_dir,
            max_results=args.max_results,
            search_depth=args.search_depth,
            max_queries=args.max_queries,
            resolve_unlisted_dois=not args.skip_crossref,
        )
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if summary["failed_query_count"] == 0 else 1
    if args.command == "verify-pdf":
        report = verify_pdf_identity(args.pdf, expected_doi=args.doi, expected_title=args.title)
        _write_json(args.out, report)
        print(json.dumps({"status": report["status"], "pdf_readable": report["pdf_readable"], "doi_matches": report["doi_matches"]}))
        return 0 if report["status"] == "main_article_candidate" else 1
    if args.command == "import-mineru":
        report = import_mineru_export(args.export_dir, output_dir=args.out_dir)
        print(json.dumps({"source_markdown": report["source_markdown"], "image_count": len(report["images"])}))
        return 0
    if args.command == "parse-mineru-vlm":
        token = os.environ.get(args.token_env)
        if not token:
            raise ValueError(f"MinerU API token environment variable is not set: {args.token_env}")
        report = parse_pdf_with_mineru_vlm(
            args.pdf,
            output_dir=args.out_dir,
            token=token,
            base_url=args.base_url,
            language=args.language,
            pages=args.pages,
            ocr=args.ocr,
            formula=not args.no_formula,
            table=not args.no_table,
            timeout=args.timeout,
            resume=args.resume,
        )
        print(json.dumps({"source_markdown": report["source_markdown"], "image_count": report["image_count"], "task_id": report.get("task_id")}))
        return 0
    if args.command == "run-pipeline":
        client = _client_from_args(args)
        mineru_token = os.environ.get(args.mineru_token_env)
        mineru_options = None
        if mineru_token:
            mineru_options = {
                "token": mineru_token,
                "base_url": args.mineru_base_url,
                "language": args.mineru_language,
                "pages": args.mineru_pages,
                "ocr": args.mineru_ocr,
                "formula": not args.mineru_no_formula,
                "table": not args.mineru_no_table,
                "timeout": args.mineru_timeout,
            }
        summary = run_manifest_pipeline(args.manifest, output_root=args.out_root, client=client, resume=args.resume, keep_going=args.keep_going, stop_after=args.stop_after, mineru_options=mineru_options)
        print(json.dumps({"result_count": summary["result_count"], "failure_count": summary["failure_count"]}))
        return 0 if summary["failure_count"] == 0 else 1
    if args.command == "review-cases":
        client = _client_from_args(args)
        cases = [ReviewCase.from_directory(path) for path in args.case_dir]
        results = run_review_batch(
            cases,
            output_root=args.out_root,
            client=client,
            resume=args.resume,
            keep_going=args.keep_going,
        )
        failed = sum(result.status == "failed" for result in results)
        print(json.dumps({"case_count": len(results), "failure_count": failed, "decisions": [result.decision for result in results]}))
        return 0 if failed == 0 else 1
    if args.command in {"audit-release", "package-release"}:
        cases = _load_release_manifest(args.manifest)
        if args.command == "audit-release":
            report = audit_release_cases(cases)
            _write_json(args.out, report)
            print(json.dumps({"case_count": report["case_count"], "blocker_count": report["blocker_count"], "passed": report["passed"]}))
            return 0 if report["passed"] else 1
        report = package_accepted_cases(cases, output_dir=args.out_dir)
        print(json.dumps({"case_count": report["case_count"], "submission_root": report["submission_root"], "internal_root": report["internal_root"]}))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def audit_json(case_root: Path, output_path: Path) -> int:
    files = sorted(case_root.rglob("*.json"))
    rows: list[dict[str, Any]] = []
    for path in files:
        issues = validate_json_file(path)
        rows.append({"path": str(path), "valid": not issues, "issues": [issue.to_dict() for issue in issues]})
    report = {"report_name": "raw_case_schema_audit", "case_root": str(case_root), "file_count": len(files), "valid_count": sum(row["valid"] for row in rows), "invalid_count": sum(not row["valid"] for row in rows), "rows": rows}
    _write_json(output_path, report)
    print(json.dumps({key: report[key] for key in ("file_count", "valid_count", "invalid_count")}, ensure_ascii=False))
    return 0 if report["invalid_count"] == 0 and report["file_count"] > 0 else 1


def _model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default="openai-compatible")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible base URL; otherwise OPENAI_BASE_URL is used.")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Name of the environment variable containing the API key.")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument("--api-protocol", choices=["chat_completions", "responses"], default="chat_completions")


def _mineru_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mineru-token-env", default="MINERU_API_TOKEN")
    parser.add_argument("--mineru-base-url", default=None)
    parser.add_argument("--mineru-language", default="en")
    parser.add_argument("--mineru-pages", default=None)
    parser.add_argument("--mineru-ocr", action="store_true")
    parser.add_argument("--mineru-no-formula", action="store_true")
    parser.add_argument("--mineru-no-table", action="store_true")
    parser.add_argument("--mineru-timeout", type=float, default=1800.0)


def _client_from_args(args: argparse.Namespace) -> OpenAICompatibleClient:
    from openai import OpenAI

    key = os.environ.get(args.api_key_env)
    if not key:
        raise ValueError(f"API key environment variable is not set: {args.api_key_env}")
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")
    options = {"api_key": key, "timeout": args.timeout, "max_retries": args.max_retries}
    if base_url:
        options["base_url"] = base_url
    sdk = OpenAI(**options)
    return OpenAICompatibleClient(
        client=sdk,
        provider_name=args.provider,
        model=args.model,
        max_output_tokens=args.max_output_tokens,
        api_protocol=args.api_protocol,
    )


def _load_release_manifest(path: Path) -> list[ReleaseCase]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = value.get("cases") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Release manifest must contain a cases array.")
    cases: list[ReleaseCase] = []
    for row in rows:
        cases.append(ReleaseCase(str(row["archive_mechanism"]), _resolve(path, row["case_dir"]), _resolve(path, row["review_dir"])))
    return cases


def _resolve(manifest: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (manifest.parent / path).resolve()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

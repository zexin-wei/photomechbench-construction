"""Command-line entry point for the raw-case construction pipeline."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .pipeline import run_manifest_pipeline
from .provider import OpenAICompatibleClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photomechbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser(
        "run-pipeline",
        help="Run the complete manifest-driven raw-case construction pipeline.",
    )
    pipeline.add_argument("--manifest", type=Path, required=True)
    pipeline.add_argument("--out-root", type=Path, required=True)
    pipeline.add_argument("--resume", action="store_true")
    pipeline.add_argument("--keep-going", action="store_true")
    _mineru_args(pipeline)
    _model_args(pipeline)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run-pipeline":
        raise AssertionError(f"Unhandled command: {args.command}")

    client = _client_from_args(args)
    mineru_token = os.environ.get(args.mineru_token_env)
    mineru_options = None
    if mineru_token:
        mineru_options = {
            "token": mineru_token,
            "base_url": args.mineru_base_url,
            "language": args.mineru_language,
            "timeout": args.mineru_timeout,
        }

    summary = run_manifest_pipeline(
        args.manifest,
        output_root=args.out_root,
        client=client,
        resume=args.resume,
        keep_going=args.keep_going,
        mineru_options=mineru_options,
    )
    print(
        json.dumps(
            {
                "result_count": summary["result_count"],
                "failure_count": summary["failure_count"],
            }
        )
    )
    return 0 if summary["failure_count"] == 0 else 1


def _model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default="openai-compatible")
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible base URL; otherwise OPENAI_BASE_URL is used.",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Name of the environment variable containing the API key.",
    )
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--max-output-tokens", type=int, default=8192)
    parser.add_argument(
        "--api-protocol",
        choices=["chat_completions", "responses"],
        default="chat_completions",
    )


def _mineru_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mineru-token-env", default="MINERU_API_TOKEN")
    parser.add_argument("--mineru-base-url", default=None)
    parser.add_argument("--mineru-language", default="en")
    parser.add_argument("--mineru-timeout", type=float, default=1800.0)


def _client_from_args(args: argparse.Namespace) -> OpenAICompatibleClient:
    from openai import OpenAI

    key = os.environ.get(args.api_key_env)
    if not key:
        raise ValueError(f"API key environment variable is not set: {args.api_key_env}")
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")
    options = {
        "api_key": key,
        "timeout": args.timeout,
        "max_retries": args.max_retries,
    }
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


if __name__ == "__main__":
    raise SystemExit(main())

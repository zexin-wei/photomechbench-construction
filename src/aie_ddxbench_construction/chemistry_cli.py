"""CLI entry point for RDKit validation in an external Python runtime.

The command prevents recursive fallback and prints one JSON-safe validation
report to stdout. It does not call a language model or write case files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from .chemistry import validate_smiles_with_rdkit


def main(argv: list[str] | None = None) -> int:
    """Run one RDKit validation request and print its JSON report."""
    parser = argparse.ArgumentParser(description="Validate a SMILES string with the current Python RDKit runtime.")
    parser.add_argument("--smiles", required=True)
    parser.add_argument("--expected-formula")
    parser.add_argument("--comparison-smiles")
    args = parser.parse_args(argv)

    report = validate_smiles_with_rdkit(
        args.smiles,
        expected_formula=args.expected_formula,
        comparison_smiles=args.comparison_smiles,
        allow_runtime_fallback=False,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["runtime_source"] = report.get("runtime_source") or "current_python"
    report["runtime_label"] = report.get("runtime_label") or sys.executable
    report["rdkit_runtime_label"] = report["runtime_label"]
    json.dump(report, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

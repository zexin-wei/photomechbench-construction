"""Private external-RDKit command for identity keys."""

from __future__ import annotations

import argparse
import json

from .identity import _current_identity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smiles", required=True)
    args = parser.parse_args()
    print(json.dumps(_current_identity(args.smiles), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

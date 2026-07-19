"""Private command used by :mod:`depiction` in an external RDKit runtime."""

from __future__ import annotations

import argparse
from pathlib import Path

from .depiction import _render_current


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smiles", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=900)
    parser.add_argument("--height", type=int, default=600)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _render_current(args.smiles, args.output, (args.width, args.height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

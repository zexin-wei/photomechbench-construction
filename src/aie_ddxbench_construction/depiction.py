"""Render a validated SMILES with the configured RDKit runtime."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from .chemistry import (
    RDKIT_CONDA_ENV,
    RDKIT_PYTHON_ENV,
    external_runtime_environment,
)


def render_smiles(
    smiles: str,
    output_path: Path,
    *,
    size: tuple[int, int] = (900, 600),
    runtime_env: Mapping[str, str] | None = None,
) -> dict[str, str | int | bool]:
    """Render one molecule locally or through an explicitly configured runtime."""
    env = runtime_env if runtime_env is not None else os.environ
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _render_current(smiles, output_path, size)
        return _report(output_path, "current_python", sys.executable)
    except ImportError:
        pass

    python_path = str(env.get(RDKIT_PYTHON_ENV) or "").strip()
    conda_env = str(env.get(RDKIT_CONDA_ENV) or "").strip()
    base = [
        "-m",
        "aie_ddxbench_construction.depiction_cli",
        "--smiles",
        smiles,
        "--output",
        str(output_path.resolve()),
        "--width",
        str(size[0]),
        "--height",
        str(size[1]),
    ]
    if python_path:
        _run([python_path, *base], runtime_env=env)
        return _report(output_path, "external_python", python_path)
    if conda_env:
        _run(["conda", "run", "-n", conda_env, "python", *base], runtime_env=env)
        return _report(output_path, "conda_env", conda_env)
    raise RuntimeError(
        "RDKit is unavailable. Configure PHOTOMECHBENCH_RDKIT_PYTHON or "
        "PHOTOMECHBENCH_RDKIT_CONDA_ENV before rendering."
    )


def _render_current(smiles: str, output_path: Path, size: tuple[int, int]) -> None:
    try:
        from rdkit import Chem  # type: ignore
        from rdkit.Chem import AllChem, Draw  # type: ignore
    except Exception as exc:
        raise ImportError(str(exc)) from exc
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError("RDKit could not parse the SMILES for depiction.")
    AllChem.Compute2DCoords(molecule)
    image = Draw.MolToImage(molecule, size=size)
    image.save(output_path)


def _run(command: list[str], *, runtime_env: Mapping[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=external_runtime_environment(runtime_env),
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "RDKit depiction failed").strip()
        raise RuntimeError(message)


def _report(path: Path, source: str, label: str) -> dict[str, str | int | bool]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("RDKit depiction did not create a non-empty image.")
    return {
        "success": True,
        "path": str(path),
        "bytes": path.stat().st_size,
        "runtime_source": source,
        "runtime_label": label,
    }

"""RDKit-derived structure identity keys for dataset-level duplicate audit."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Mapping

from .chemistry import RDKIT_CONDA_ENV, RDKIT_PYTHON_ENV, external_runtime_environment


def structure_identity(smiles: str, *, runtime_env: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = runtime_env if runtime_env is not None else os.environ
    try:
        return _current_identity(smiles)
    except ImportError:
        pass
    python_path = str(env.get(RDKIT_PYTHON_ENV) or "").strip()
    conda_env = str(env.get(RDKIT_CONDA_ENV) or "").strip()
    base = ["-m", "aie_ddxbench_construction.identity_cli", "--smiles", smiles]
    if python_path:
        return _external([python_path, *base], "external_python", python_path, runtime_env=env)
    if conda_env:
        return _external(
            ["conda", "run", "-n", conda_env, "python", *base],
            "conda_env",
            conda_env,
            runtime_env=env,
        )
    return {"rdkit_available": False, "error": "RDKit runtime is not configured", "raw_smiles": smiles}


def _current_identity(smiles: str) -> dict[str, Any]:
    try:
        from rdkit import Chem  # type: ignore
    except Exception as exc:
        raise ImportError(str(exc)) from exc
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {"rdkit_available": True, "parse_success": False, "raw_smiles": smiles}
    canonical = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
    try:
        inchi_key = Chem.MolToInchiKey(molecule)
    except Exception:
        inchi_key = ""
    fragments = list(Chem.GetMolFrags(molecule, asMols=True, sanitizeFrags=True))
    largest = max(fragments, key=lambda item: (item.GetNumHeavyAtoms(), item.GetNumAtoms())) if fragments else molecule
    largest_smiles = Chem.MolToSmiles(largest, canonical=True, isomericSmiles=True)
    try:
        largest_inchi_key = Chem.MolToInchiKey(largest)
    except Exception:
        largest_inchi_key = ""
    return {
        "rdkit_available": True,
        "parse_success": True,
        "raw_smiles": smiles,
        "canonical_smiles": canonical,
        "inchi_key": inchi_key,
        "inchi_key14": inchi_key.split("-")[0] if inchi_key else "",
        "structure_key": inchi_key or canonical,
        "largest_fragment_smiles": largest_smiles,
        "largest_fragment_inchi_key": largest_inchi_key,
        "largest_fragment_key": largest_inchi_key or largest_smiles,
        "component_count": len(fragments) if fragments else 1,
        "has_dot_components": "." in smiles,
        "runtime_source": "current_python",
        "runtime_label": sys.executable,
    }


def _external(
    command: list[str],
    source: str,
    label: str,
    *,
    runtime_env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=external_runtime_environment(runtime_env),
    )
    if completed.returncode != 0:
        return {"rdkit_available": False, "error": (completed.stderr or completed.stdout).strip(), "runtime_source": source, "runtime_label": label}
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("External identity runtime did not return an object.")
    value["runtime_source"] = source
    value["runtime_label"] = label
    return value

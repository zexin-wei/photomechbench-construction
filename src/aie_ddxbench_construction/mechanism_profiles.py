"""Load and validate the 11 packaged mechanism profiles."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .vocabulary import OFFICIAL_MECHANISMS

REQUIRED_PROFILE_KEYS = {
    "mechanism",
    "description",
    "queries",
    "mechanism_signal_terms",
    "positive_evidence",
    "insufficient_evidence",
    "common_confusions",
    "triage_policy",
}


def load_mechanism_profile(mechanism: str) -> dict[str, Any]:
    if mechanism not in OFFICIAL_MECHANISMS:
        raise ValueError(f"Unknown mechanism: {mechanism}")
    path = files("aie_ddxbench_construction").joinpath(f"profiles/{mechanism}.json")
    profile = json.loads(path.read_text(encoding="utf-8"))
    issues = validate_mechanism_profile(profile, expected_mechanism=mechanism)
    if issues:
        raise ValueError(f"Invalid mechanism profile {mechanism}: {'; '.join(issues)}")
    return profile


def load_all_mechanism_profiles() -> dict[str, dict[str, Any]]:
    return {mechanism: load_mechanism_profile(mechanism) for mechanism in OFFICIAL_MECHANISMS}


def validate_mechanism_profile(profile: Any, *, expected_mechanism: str | None = None) -> list[str]:
    if not isinstance(profile, dict):
        return ["profile_not_object"]
    issues: list[str] = []
    missing = sorted(REQUIRED_PROFILE_KEYS - set(profile))
    if missing:
        issues.append(f"missing_keys:{','.join(missing)}")
    mechanism = profile.get("mechanism")
    if mechanism not in OFFICIAL_MECHANISMS:
        issues.append(f"invalid_mechanism:{mechanism}")
    if expected_mechanism and mechanism != expected_mechanism:
        issues.append(f"mechanism_filename_mismatch:{mechanism}")
    for key in ("queries", "mechanism_signal_terms", "positive_evidence", "insufficient_evidence", "common_confusions"):
        value = profile.get(key)
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
            issues.append(f"invalid_nonempty_string_list:{key}")
    return issues

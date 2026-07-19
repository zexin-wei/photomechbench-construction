from __future__ import annotations

from aie_ddxbench_construction.mechanism_profiles import load_all_mechanism_profiles
from aie_ddxbench_construction.vocabulary import OFFICIAL_MECHANISMS


def test_all_official_profiles_load() -> None:
    profiles = load_all_mechanism_profiles()
    assert tuple(profiles) == OFFICIAL_MECHANISMS
    assert all(profile["queries"] for profile in profiles.values())


def test_profiles_do_not_define_final_labels() -> None:
    profiles = load_all_mechanism_profiles()
    assert set(profiles) == set(OFFICIAL_MECHANISMS)

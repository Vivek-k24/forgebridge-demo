from __future__ import annotations

from collections import defaultdict

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge.identity_catalog_worker_v3 import (
    _finalize_trim_observations,
    _strict_trim_value,
    extract_carsdirect_trims,
    extract_kbb_trims,
    identity_dimensions,
    model_variants,
)


def _observation(label: str, provider: str = "kbb"):
    return {
        legacy.normalized_key(label): {
            provider: (label, {"status": "cached", "source_model": "Example"})
        }
    }


def _merge(*items):
    result = defaultdict(dict)
    for item in items:
        for key, provider_map in item.items():
            result[key].update(provider_map)
    return result


def _labels(observations):
    return {
        label
        for provider_map in observations.values()
        for label, _evidence in provider_map.values()
    }


def test_v3_rejects_singular_consumer_review_and_engine_displacement() -> None:
    assert _strict_trim_value("Based on 1 Consumer Review") is None
    assert _strict_trim_value("Based on 42 Consumer Reviews") is None
    assert _strict_trim_value("3.0L") is None
    assert _strict_trim_value("3.2L") is None
    assert _strict_trim_value("EX-L") == "EX-L"


def test_kbb_parser_preserves_multiple_body_styles_for_civic() -> None:
    raw = b"""
    <a href="/honda/civic/2026/lx-sedan-4d/">LX</a>
    <a href="/honda/civic/2026/sport-sedan-4d/">Sport Sedan 4D</a>
    <a href="/honda/civic/2026/sport-hatchback-4d/">Sport Hatchback 4D</a>
    <a href="/honda/civic/2026/sport-touring-hybrid-hatchback-4d/">
      Sport Touring Hybrid Hatchback 4D
    </a>
    <a href="/honda/civic/2026/type-r-hatchback-4d/">Type R Hatchback 4D</a>
    """
    labels = set(extract_kbb_trims(raw, "Honda", "Civic", 2026))

    assert "Sedan LX" in labels
    assert "Sedan Sport" in labels
    assert "Hatchback Sport" in labels
    assert "Hatchback Sport Touring Hybrid" in labels
    assert "Type R" in labels


def test_carsdirect_parser_preserves_explicit_body_style() -> None:
    raw = b"""
    <select>
      <option>LX 4dr Sedan</option>
      <option>Sport 4dr Sedan</option>
      <option>Sport 4dr Hatchback</option>
    </select>
    """
    labels = set(extract_carsdirect_trims(raw, "Civic", 2026))
    assert "Sedan LX" in labels
    assert "Sedan Sport" in labels
    assert "Hatchback Sport" in labels


def test_multiple_body_styles_keep_body_and_remove_generic_duplicates() -> None:
    observations = _merge(
        _observation("Sedan LX"),
        _observation("Sedan Sport"),
        _observation("Hatchback Sport"),
        _observation("LX", "carsdirect"),
        _observation("Sport", "carsdirect"),
        _observation("Type R"),
    )
    finalized = _finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Civic", "Civic Type R"]},
    )
    labels = _labels(finalized)

    assert "Sedan LX" in labels
    assert "Sedan Sport" in labels
    assert "Hatchback Sport" in labels
    assert "Type R" in labels
    assert "LX" not in labels
    assert "Sport" not in labels


def test_single_body_style_collapses_to_grade() -> None:
    observations = _merge(
        _observation("Sedan LX"),
        _observation("Sedan Sport"),
        _observation("Sedan Touring"),
    )
    finalized = _finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Accord"]},
    )
    assert _labels(finalized) == {"LX", "Sport", "Touring"}


def test_specific_hybrid_grades_remove_generic_hybrid_row() -> None:
    observations = _merge(
        _observation("Hybrid", "fueleconomy_gov"),
        _observation("Sport Hybrid"),
        _observation("EX-L Hybrid"),
        _observation("Touring Hybrid"),
    )
    finalized = _finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Accord", "Accord Hybrid"]},
    )
    labels = _labels(finalized)

    assert "Hybrid" not in labels
    assert {"Sport Hybrid", "EX-L Hybrid", "Touring Hybrid"} <= labels


def test_fueleconomy_generic_grade_yields_to_consumer_hybrid_grade() -> None:
    observations = _merge(
        _observation("TrailSport", "fueleconomy_gov"),
        _observation("TrailSport Hybrid", "kbb"),
        _observation("Sport", "fueleconomy_gov"),
        _observation("Sport", "kbb"),
        _observation("Sport Hybrid", "kbb"),
    )
    finalized = _finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["CR-V"]},
    )
    labels = _labels(finalized)

    assert "TrailSport" not in labels
    assert "TrailSport Hybrid" in labels
    assert "Sport" in labels
    assert "Sport Hybrid" in labels


def test_package_extensions_are_not_promoted_without_independent_model_label_support() -> None:
    passport = _merge(
        _observation("RTL"),
        _observation("RTL Blackout"),
        _observation("TrailSport"),
        _observation("TrailSport Blackout"),
        _observation("TrailSport Elite"),
        _observation("TrailSport Elite Blackout"),
    )
    finalized = _finalize_trim_observations(
        passport,
        {
            "nhtsa_vpic": ["Passport"],
            "fueleconomy_gov": ["Passport AWD Trailsport"],
        },
    )
    assert _labels(finalized) == {"RTL", "TrailSport", "TrailSport Elite"}

    pilot = _merge(
        _observation("Touring"),
        _observation("Touring Blackout"),
    )
    pilot_finalized = _finalize_trim_observations(
        pilot,
        {
            "nhtsa_vpic": ["Pilot"],
            "fueleconomy_gov": ["Pilot AWD Touring/Elite/Black"],
        },
    )
    assert "Touring Blackout" in _labels(pilot_finalized)


def test_truncated_single_letter_s_suffix_is_removed_when_base_exists() -> None:
    observations = _merge(
        _observation("Touring"),
        _observation("Touring S"),
        _observation("TrailSport"),
        _observation("TrailSport S"),
        _observation("Type S"),
    )
    finalized = _finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Pilot"]},
    )
    labels = _labels(finalized)

    assert "Touring S" not in labels
    assert "TrailSport S" not in labels
    assert "Touring" in labels
    assert "TrailSport" in labels
    assert "Type S" in labels


def test_source_model_variants_recover_trailsport_fcev_and_slash_grades() -> None:
    assert model_variants("CR-V", "CR-V AWD TrailSport") == ("TrailSport",)
    assert model_variants("CR-V", "CR-V e-FCEV") == ("e:FCEV",)
    assert model_variants(
        "Pilot",
        "Pilot AWD Touring/Elite/Black",
    ) == ("Touring", "Elite", "Black Edition")


def test_export_dimensions_keep_grade_body_and_powertrain_separate() -> None:
    assert identity_dimensions("Sedan Sport Hybrid") == {
        "marketed_label": "Sedan Sport Hybrid",
        "grade": "Sport",
        "body_style": "Sedan",
        "powertrain_variant": "Hybrid",
    }
    assert identity_dimensions("Type R") == {
        "marketed_label": "Type R",
        "grade": "Type R",
    }

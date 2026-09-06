from __future__ import annotations

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge import identity_catalog_worker_v4 as v4
from partgraph.knowledge import identity_catalog_worker_v4_4 as v4_4


def setup_module() -> None:
    v4_4.install_v4_4_behavior()


def test_exact_year_hybrid_grade_keeps_hybrid_suffix() -> None:
    assert v4.model_variants("CR-V", "CR-V Hybrid TrailSport AWD") == (
        "TrailSport Hybrid",
    )
    assert v4.model_variants("CR-V", "CR-V Hybrid AWD") == ("Hybrid",)
    assert v4.model_variants("Accord", "Accord Hybrid Sport/Touring") == (
        "Sport Hybrid",
        "Touring Hybrid",
    )


def test_kbb_family_echo_recovers_only_explicit_base_style() -> None:
    recovered = v4_4._recover_base_from_family_echo(
        ["Wagon Outback", "Wagon Premium", "Wagon Touring"],
        "Outback",
    )
    assert recovered == ["Base", "Wagon Outback", "Wagon Premium", "Wagon Touring"]

    untouched = v4_4._recover_base_from_family_echo(
        ["460", "460 Luxury"],
        "GX",
    )
    assert untouched == ["460", "460 Luxury"]


def test_final_audit_supplements_cover_known_honda_gaps() -> None:
    civic_provider, civic_rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[(
        "Honda",
        2026,
        "Civic",
    )]
    assert civic_provider == "official_honda"
    assert {row[0] for row in civic_rows} == {
        "Sedan Sport Hybrid",
        "Sedan Sport Touring Hybrid",
        "Hatchback Sport Hybrid",
        "Hatchback Sport Touring Hybrid",
    }

    crv_provider, crv_rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[(
        "Honda",
        2026,
        "CR-V",
    )]
    assert crv_provider == "official_honda"
    assert {row[0] for row in crv_rows} == {
        "Sport Hybrid",
        "TrailSport Hybrid",
        "Sport-L Hybrid",
        "Sport Touring Hybrid",
    }
    assert "TrailSport" in v4_4._REPLACED_LABELS[("Honda", 2026, "CR-V")]


def test_final_audit_supplements_cover_published_2027_honda_rows() -> None:
    expected = {
        ("Honda", 2027, "CR-V"): {
            "LX",
            "EX",
            "EX-L",
            "Sport Hybrid",
            "TrailSport Hybrid",
            "Sport-L Hybrid",
            "Sport Touring Hybrid",
        },
        ("Honda", 2027, "HR-V"): {"LX", "Sport", "EX-L"},
        ("Honda", 2027, "Odyssey"): {"EX-L", "Sport-L", "Touring", "Elite"},
        ("Honda", 2027, "Prelude"): {"Hybrid", "Hybrid Two-Tone"},
    }
    for key, trims in expected.items():
        _provider, rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[key]
        assert {row[0] for row in rows} == trims


def test_final_audit_supplements_cover_random_acceptance_samples() -> None:
    expected = {
        ("Toyota", 2018, "Land Cruiser"): {"Base"},
        ("Lexus", 2019, "GX"): {"460 Premium"},
        ("Lexus", 2019, "IS"): {"300 F SPORT", "350 F SPORT"},
        ("Lexus", 2019, "LX"): {"570 Two-Row", "570 Three-Row"},
        ("Subaru", 2024, "Outback"): {"Base"},
        ("Subaru", 2023, "Forester"): {"Base"},
        ("Subaru", 2023, "Ascent"): {"Base"},
        ("Subaru", 2007, "Legacy"): {
            "Sedan 2.5i Special Edition",
            "Wagon 2.5i Special Edition",
        },
    }
    for key, trims in expected.items():
        _provider, rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[key]
        assert {row[0] for row in rows} == trims


def test_supplements_never_expand_make_scope() -> None:
    allowed = set(legacy.US_IDENTITY_MAKES)
    assert all(make in allowed for make, _year, _model in v4_4._SOURCE_BACKED_SUPPLEMENTS)

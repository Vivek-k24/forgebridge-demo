from __future__ import annotations

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge import identity_catalog_worker_v3 as v3
from partgraph.knowledge import identity_catalog_worker_v4 as v4
from partgraph.knowledge import identity_catalog_worker_v4_2 as v4_2
from partgraph.knowledge import identity_catalog_worker_v4_4 as v4_4
from partgraph.knowledge import identity_catalog_worker_v4_5 as v4_5


def setup_module() -> None:
    v4_5.install_v4_5_behavior()


def _evidence(source_model: str) -> dict[str, object]:
    return {"status": "cached", "source_model": source_model}


def test_v4_5_preserves_v4_2_collection_boundary() -> None:
    assert v4_4._BASE_COLLECT_MAKE_YEAR is v4_2._collect_make_year


def test_v4_5_installed_finalizer_reconciles_residual_source_spellings() -> None:
    observations = {
        legacy.normalized_key("Sedan VP"): {
            "kbb": ("Sedan VP", _evidence("Accord")),
        },
        legacy.normalized_key("Sedan Value Package"): {
            "carsdirect": ("Sedan Value Package", _evidence("Accord")),
        },
        legacy.normalized_key("Coupe EX"): {
            "kbb": ("Coupe EX", _evidence("Accord")),
        },
    }

    finalized = v3._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Accord"]},
    )

    assert "sedan value package" not in finalized
    assert set(finalized["sedan vp"]) == {"kbb", "carsdirect"}
    assert {
        label for label, _evidence_row in finalized["sedan vp"].values()
    } == {"Sedan VP"}


def test_v4_5_normalizes_remaining_package_presentations() -> None:
    assert v4._normalize_selection_label("w/Technology") == "Technology"
    assert v4._normalize_selection_label("Tech & A-Spec Pkgs") == "Technology A-Spec"
    assert (
        v4._normalize_selection_label("Technology & AcuraWatch Plus Pkg")
        == "Technology"
    )


def test_v4_5_removes_liftback_body_presentation() -> None:
    assert v4._normalize_selection_label("Liftback") == "Base"
    assert v4._normalize_selection_label("Turbo Liftback") == "Turbo"
    assert v4._normalize_selection_label("Hatchback GT Liftback") == "Hatchback GT"
    assert (
        v4._normalize_selection_label("Hatchback Limited Edition Turbo Liftback")
        == "Hatchback Limited Edition Turbo"
    )


def test_v4_5_collapses_historical_kbb_sport_body_presentation_with_support() -> None:
    observations = {
        legacy.normalized_key("Sedan WRX"): {
            "kbb": ("Sedan WRX", _evidence("Impreza")),
        },
        legacy.normalized_key("Sedan 2.5i"): {
            "kbb": ("Sedan 2.5i", _evidence("Impreza")),
        },
        legacy.normalized_key("Wagon WRX Sport"): {
            "kbb": ("Wagon WRX Sport", _evidence("Impreza")),
        },
        legacy.normalized_key("Wagon 2.5i Sport"): {
            "kbb": ("Wagon 2.5i Sport", _evidence("Impreza")),
        },
    }

    finalized = v3._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Impreza"]},
    )

    assert "wagon wrx sport" not in finalized
    assert "wagon 2 5i sport" not in finalized
    assert "wagon wrx" in finalized
    assert "wagon 2 5i" in finalized


def test_v4_5_does_not_strip_real_sport_when_body_group_has_other_grades() -> None:
    observations = {
        legacy.normalized_key("Sedan 2.0i Limited"): {
            "kbb": ("Sedan 2.0i Limited", _evidence("Impreza")),
        },
        legacy.normalized_key("Sedan 2.0i Sport"): {
            "kbb": ("Sedan 2.0i Sport", _evidence("Impreza")),
        },
        legacy.normalized_key("Wagon 2.0i"): {
            "kbb": ("Wagon 2.0i", _evidence("Impreza")),
        },
    }

    finalized = v3._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Impreza"]},
    )

    assert "sedan 2 0i sport" in finalized


def test_v4_5_preserves_genuine_outback_sport() -> None:
    observations = {
        legacy.normalized_key("Sedan L"): {
            "kbb": ("Sedan L", _evidence("Impreza")),
        },
        legacy.normalized_key("Wagon L Sport"): {
            "kbb": ("Wagon L Sport", _evidence("Impreza")),
        },
        legacy.normalized_key("Wagon Outback Sport"): {
            "kbb": ("Wagon Outback Sport", _evidence("Impreza")),
        },
    }

    finalized = v3._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Impreza"]},
    )

    assert "wagon l" in finalized
    assert "wagon outback sport" in finalized


def test_final_sample_supplements_cover_body_presentation_artifacts() -> None:
    expected = {
        ("Hyundai", 2010, "Accent"): {"Hatchback Blue"},
        ("Lexus", 2010, "IS"): {
            "Sedan 250",
            "Sedan 350",
            "Convertible 250",
            "Convertible 350",
        },
        ("Subaru", 2006, "Impreza"): {"Wagon Outback Sport Special Edition"},
        ("Subaru", 2008, "Impreza"): {"Wagon WRX STI"},
        ("Subaru", 2010, "Impreza"): {
            "Wagon WRX STI",
            "Wagon WRX STI Special Edition",
        },
    }
    for key, trims in expected.items():
        provider, rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[key]
        assert provider == "edmunds_reference"
        assert {trim for trim, _url in rows} == trims


def test_2019_es_premium_package_artifacts_are_removed() -> None:
    assert v4_5._FINAL_SAMPLE_REPLACEMENTS[("Lexus", 2019, "ES")] == {
        "300h Premium",
        "350 Premium",
    }
    provider, rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[("Lexus", 2019, "ES")]
    assert provider == "lexus_official"
    assert {trim for trim, _url in rows} == {"300h", "350", "350 F Sport"}


def test_2019_lc_base_page_artifact_is_removed() -> None:
    assert v4_5._FINAL_SAMPLE_REPLACEMENTS[("Lexus", 2019, "LC")] == {"Base"}
    provider, rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[("Lexus", 2019, "LC")]
    assert provider == "lexus_official"
    assert {trim for trim, _url in rows} == {"500", "500h"}


def test_2012_legacy_only_keeps_limited_gt_grade() -> None:
    assert v4_5._FINAL_SAMPLE_REPLACEMENTS[("Subaru", 2012, "Legacy")] == {
        "2.5GT"
    }
    provider, rows = v4_4._SOURCE_BACKED_SUPPLEMENTS[("Subaru", 2012, "Legacy")]
    assert provider == "edmunds_reference"
    assert {trim for trim, _url in rows} == {"2.5GT Limited"}

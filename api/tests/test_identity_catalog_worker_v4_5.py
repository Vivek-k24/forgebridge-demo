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

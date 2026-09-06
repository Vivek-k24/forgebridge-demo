from __future__ import annotations

from partgraph.knowledge import identity_catalog_worker_v4_4 as v4_4
from partgraph.knowledge import identity_catalog_worker_v4_5 as v4_5


def setup_module() -> None:
    v4_5.install_v4_5_behavior()


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

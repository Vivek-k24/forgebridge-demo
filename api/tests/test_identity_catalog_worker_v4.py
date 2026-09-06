from __future__ import annotations

from collections import defaultdict

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge import identity_catalog_worker_v3 as v3
from partgraph.knowledge import identity_catalog_worker_v4 as v4
from partgraph.knowledge import identity_catalog_worker_v4_1 as v4_1


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


def setup_module() -> None:
    v4_1.install_v4_1_behavior()


def test_hybrid_slash_source_keeps_hybrid_on_each_grade() -> None:
    assert v4.model_variants(
        "Accord",
        "Accord Hybrid Sport/Touring",
    ) == ("Sport Hybrid", "Touring Hybrid")


def test_base_performance_aliases_do_not_create_base_si_or_base_type_r() -> None:
    assert v4.combine_trim_variant("Sedan Base", "Si") == "Si"
    assert v4.combine_trim_variant("Hatchback Base", "Type R") == "Type R"


def test_body_synonyms_do_not_create_false_multiple_body_styles() -> None:
    observations = _merge(
        _observation("SUV Sport"),
        _observation("Sport Utility EX"),
        _observation("Sport Utility EX-L"),
        _observation("Sport Utility LX"),
    )
    finalized = v4._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["HR-V"]},
    )
    assert _labels(finalized) == {"Sport", "EX", "EX-L", "LX"}


def test_standalone_two_tone_is_not_a_trim() -> None:
    assert v4._strict_trim_value("2-Tone") is None
    assert v4._strict_trim_value("Sport-L") == "Sport-L"


def test_configuration_options_collapse_to_marketed_grade() -> None:
    observations = _merge(
        _observation("EX"),
        _observation("EX w/Navigation", "carsdirect"),
        _observation("LE"),
        _observation("LE 8 Passenger", "carsdirect"),
        _observation("Type S"),
        _observation("Type S w/Nav System", "carsdirect"),
    )
    finalized = v4._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Example"]},
    )
    assert _labels(finalized) == {"EX", "LE", "Type S"}


def test_leading_transmission_option_collapses_without_losing_grade() -> None:
    assert v4._normalize_selection_label("Sedan w/CVT SE") == "Sedan SE"
    assert v4._normalize_selection_label("Coupe w/5-Speed Manual EX") == "Coupe EX"


def test_trailing_kbb_sport_descriptor_collapses_when_shorter_grade_exists() -> None:
    observations = _merge(
        _observation("Coupe GS-R", "carsdirect"),
        _observation("Coupe GS-R Sport", "kbb"),
        _observation("Sedan GS-R", "carsdirect"),
    )
    finalized = v4._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["Integra"]},
    )
    assert _labels(finalized) == {"Coupe GS-R", "Sedan GS-R"}


def test_simplified_hybrid_alias_is_added_after_family_is_observed() -> None:
    v4._CURRENT_MAKE = "Honda"
    v4._HYBRID_FAMILIES.add(("Honda", legacy.normalized_key("CR-V")))
    aliases = v4._source_model_aliases(
        "CR-V",
        {"fueleconomy_gov": ["CR-V AWD"]},
    )
    assert aliases == ["CR-V", "CR-V Hybrid"]


def test_v4_body_map_is_installed_for_v3_dimension_parser() -> None:
    assert v3._split_body_prefix("Sport Utility Limited") == ("SUV", "Limited")
    assert v3._split_body_prefix("SUV Sport") == ("SUV", "Sport")

from __future__ import annotations

from collections import defaultdict

from partgraph.knowledge import identity_catalog_worker as legacy
from partgraph.knowledge import identity_catalog_worker_v3 as v3
from partgraph.knowledge import identity_catalog_worker_v4 as v4
from partgraph.knowledge import identity_catalog_worker_v4_3 as v4_3


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
    v4_3.install_v4_3_behavior()


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
    assert v4._normalize_selection_label("w/ Manual N Base") == "N"


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


def test_simplified_hybrid_alias_requires_current_year_evidence() -> None:
    assert v4._source_model_aliases(
        "CR-V",
        {"fueleconomy_gov": ["CR-V AWD"]},
    ) == ["CR-V"]
    assert v4._source_model_aliases(
        "CR-V",
        {"fueleconomy_gov": ["CR-V Hybrid AWD"]},
    ) == ["CR-V", "CR-V Hybrid"]


def test_family_name_is_not_repeated_inside_trim() -> None:
    observations = _merge(
        _observation("IS 350 F SPORT"),
        _observation("IS 350 F SPORT Design", "carsdirect"),
    )
    finalized = v4._finalize_trim_observations(
        observations,
        {"nhtsa_vpic": ["IS"]},
    )
    assert _labels(finalized) == {"350 F SPORT", "350 F SPORT Design"}
    assert v4._normalize_selection_label("Passport", "Passport") is None


def test_drivetrain_is_not_promoted_to_trim() -> None:
    assert v4._normalize_selection_label("SH-AWD") is None
    assert v4._normalize_selection_label("FWD") is None
    assert v4._normalize_selection_label("SH-AWD PMC Edition") == "PMC Edition"
    assert v4._normalize_selection_label("2.0 SH-AWD") is None


def test_marketed_package_selection_survives_configuration_cleanup() -> None:
    assert v4._normalize_selection_label("Base w/Technology Pkg") == "Technology"
    assert (
        v4._normalize_selection_label("SH-AWD w/A-Spec Advance Pkg")
        == "A-Spec Advance"
    )
    assert v4._normalize_selection_label("SH-AWD w/A-Spec Pkg") == "A-Spec"
    assert v4._normalize_selection_label("SH-AWD w/Advance Pkg") == "Advance"
    assert v4._normalize_selection_label("Type S w/Advance Pkg") == "Type S Advance"


def test_v4_3_normalizes_residual_package_presentations() -> None:
    assert v4._normalize_selection_label("w/Technology") == "Technology"
    assert v4._normalize_selection_label("Premium Package") == "Premium"
    assert v4._normalize_selection_label("Premium Pkg") == "Premium"
    assert (
        v4._normalize_selection_label("Premium & A-Spec Packages")
        == "Premium A-Spec"
    )
    assert (
        v4._normalize_selection_label("Technology Plus & A-Spec Pkgs")
        == "Technology Plus A-Spec"
    )
    assert (
        v4._normalize_selection_label("Tech & A-Spec Pkgs")
        == "Technology A-Spec"
    )
    assert v4._normalize_selection_label("Advance & Entertainment Pkgs") == "Advance"
    assert (
        v4._normalize_selection_label("Technology & Entertainment Pkgs")
        == "Technology"
    )
    assert v4._normalize_selection_label("AcuraWatch Plus Pkg") is None


def test_v4_3_collapses_known_source_package_noise() -> None:
    assert v4._normalize_selection_label("Sedan Value Package") == "Sedan VP"
    assert v4._normalize_selection_label("Base Pkg 3 & 4") == "Base"
    assert v4._normalize_selection_label("Base Pkg 3 to 6") == "Base"
    assert v4._normalize_selection_label("2 & 5") is None


def test_historical_performance_and_hybrid_artifacts_collapse() -> None:
    assert v4._normalize_selection_label("Coupe Type R Sport") == "Type R"
    assert v4._normalize_selection_label("Sedan Si Base") == "Si"
    assert v4._normalize_selection_label("Base Hybrid") == "Hybrid"
    assert v4._normalize_selection_label("Sport Hybrid Base") == "Sport Hybrid"
    assert v4._normalize_selection_label("Hybrid LE") == "LE Hybrid"


def test_engine_and_transmission_tokens_are_not_trim_dimensions() -> None:
    assert v4._normalize_selection_label("Coupe 2.4 EX") == "Coupe EX"
    assert v4._normalize_selection_label("3.2 Type S") == "Type S"
    assert v4._normalize_selection_label("LE V6 4 Speed Auto") == "LE"
    assert v4._normalize_selection_label("1.5T") is None
    assert v4._normalize_selection_label("V6") is None
    # Historical numeric marketed grades remain intact when no technical suffix
    # proves that the value is only an engine designation.
    assert v4._normalize_selection_label("3.2") == "3.2"


def test_non_trim_page_configuration_text_is_rejected() -> None:
    assert v4._normalize_selection_label("Hatchback w/0 Blind Spot Information") is None
    assert v4._normalize_selection_label("w/Solar Roof") is None
    assert v4._normalize_selection_label("Wheels") is None
    assert v4._normalize_selection_label("wheels 3.7") is None
    assert v4._normalize_selection_label("Continuously Variable Transmission") is None
    assert v4._normalize_selection_label("2011 Toyota Camry SE") is None
    # "1958" is a real Land Cruiser grade, not a year-prefixed page artifact.
    assert v4._normalize_selection_label("1958") == "1958"


def test_v4_body_map_is_installed_for_v3_dimension_parser() -> None:
    assert v3._split_body_prefix("Sport Utility Limited") == ("SUV", "Limited")
    assert v3._split_body_prefix("SUV Sport") == ("SUV", "Sport")

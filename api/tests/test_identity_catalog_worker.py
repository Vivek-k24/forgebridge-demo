from partgraph.knowledge.catalog_scope import (
    US_IDENTITY_MAKES,
    US_IDENTITY_YEAR_MAX,
    US_IDENTITY_YEAR_MIN,
    canonical_scoped_make,
)
from partgraph.knowledge.identity_catalog_worker import (
    canonicalize_model_inventory,
    combine_trim_variant,
    extract_carsdirect_trims,
    extract_kbb_trims,
    model_variant,
    trim_from_carsdirect_style,
    trim_from_kbb_style,
)


def test_active_identity_scope_is_six_requested_makes_1996_through_2027() -> None:
    assert US_IDENTITY_MAKES == (
        "Acura",
        "Honda",
        "Hyundai",
        "Lexus",
        "Subaru",
        "Toyota",
    )
    assert US_IDENTITY_YEAR_MIN == 1996
    assert US_IDENTITY_YEAR_MAX == 2027
    assert canonical_scoped_make("honda") == "Honda"
    assert canonical_scoped_make("Ford") is None


def test_model_inventory_collapses_hybrid_and_drivetrain_variants_to_base_model() -> None:
    result = canonicalize_model_inventory(
        ["Civic", "Civic Hybrid", "CR-V", "Prius Prime"],
        ["Civic", "Civic Hybrid", "CR-V 2WD", "CR-V 4WD", "Prius Prime"],
    )

    assert set(result) == {"Civic", "CR-V", "Prius Prime"}
    assert result["Civic"]["nhtsa_vpic"] == ["Civic", "Civic Hybrid"]
    assert result["Civic"]["fueleconomy_gov"] == ["Civic", "Civic Hybrid"]
    assert result["CR-V"]["fueleconomy_gov"] == ["CR-V 2WD", "CR-V 4WD"]
    assert result["Prius Prime"]["fueleconomy_gov"] == ["Prius Prime"]


def test_fueleconomy_hybrid_suffix_uses_base_model_even_if_nhtsa_only_names_base() -> None:
    result = canonicalize_model_inventory(
        ["Accord"],
        ["Accord", "Accord Hybrid"],
    )

    assert set(result) == {"Accord"}
    assert result["Accord"]["fueleconomy_gov"] == ["Accord", "Accord Hybrid"]


def test_hybrid_source_model_becomes_trim_variant_not_separate_model() -> None:
    assert model_variant("Accord", "Accord Hybrid") == "Hybrid"
    assert model_variant("Accord", "Accord") is None
    assert combine_trim_variant("Sport-L", "Hybrid") == "Sport-L Hybrid"
    assert combine_trim_variant("Base", "Hybrid") == "Hybrid"
    assert combine_trim_variant(None, "Hybrid") == "Hybrid"


def test_kbb_style_normalization_removes_body_style_not_trim_words() -> None:
    assert trim_from_kbb_style("HX Coupe 2D") == "HX"
    assert trim_from_kbb_style("LX Sport Utility 4D") == "LX"
    assert trim_from_kbb_style("Sport Touring Hatchback 4D") == "Sport Touring"
    assert trim_from_kbb_style("XLE Premium Sport Utility 4D") == "XLE Premium"


def test_kbb_trim_extractor_deduplicates_body_styles_for_same_trim() -> None:
    raw = b"""
    <a href="/honda/civic/1998/hx-coupe-2d/">HX Coupe 2D</a>
    <a href="/honda/civic/1998/dx-coupe-2d/">DX Coupe 2D</a>
    <a href="/honda/civic/1998/dx-sedan-4d/">DX Sedan 4D</a>
    <a href="/honda/civic/1998/lx-sedan-4d/">LX Sedan 4D</a>
    <a href="/honda/civic/1998/reviews/">Reviews</a>
    """

    assert extract_kbb_trims(raw, "Honda", "Civic", 1998) == ["DX", "HX", "LX"]


def test_carsdirect_style_normalization_removes_configuration_body_suffix() -> None:
    assert trim_from_carsdirect_style("CX 2dr Hatchback") == "CX"
    assert trim_from_carsdirect_style("LE 4dr Front-Wheel Drive Hybrid Sedan") == "LE"
    assert trim_from_carsdirect_style("TRD Off-Road 4x4 Double Cab") == "TRD Off-Road"
    assert trim_from_carsdirect_style("2.5L I-4 / 184 Hp") is None


def test_carsdirect_trim_extractor_collects_select_options_without_specs() -> None:
    raw = b"""
    <select>
      <option>Select a Trim</option>
      <option>Sport 4dr Sedan</option>
      <option>EX-L 4dr Sedan</option>
      <option>Sport-L 4dr Sedan</option>
      <option>Touring 4dr Sedan</option>
      <option>2.0L I-4 / 146 Hp</option>
    </select>
    """

    assert extract_carsdirect_trims(raw, "Accord Hybrid", 2026) == [
        "EX-L",
        "Sport",
        "Sport-L",
        "Touring",
    ]

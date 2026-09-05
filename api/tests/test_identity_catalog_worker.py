from partgraph.knowledge.catalog_scope import (
    US_IDENTITY_MAKES,
    US_IDENTITY_YEAR_MAX,
    US_IDENTITY_YEAR_MIN,
    canonical_scoped_make,
)
from partgraph.knowledge.identity_catalog_worker import (
    canonicalize_model_inventory,
    extract_kbb_trims,
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


def test_model_inventory_keeps_real_hybrid_model_but_collapses_drivetrain_suffix() -> None:
    result = canonicalize_model_inventory(
        ["Civic", "Civic Hybrid", "CR-V"],
        ["Civic", "Civic Hybrid", "CR-V 2WD", "CR-V 4WD"],
    )

    assert set(result) == {"Civic", "Civic Hybrid", "CR-V"}
    assert result["Civic Hybrid"]["fueleconomy_gov"] == ["Civic Hybrid"]
    assert result["CR-V"]["fueleconomy_gov"] == ["CR-V 2WD", "CR-V 4WD"]


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

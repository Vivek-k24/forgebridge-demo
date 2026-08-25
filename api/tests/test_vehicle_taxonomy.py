import pytest

from partgraph.vehicle.taxonomy import (
    UnsupportedBrandError,
    canonical_body_style,
    canonical_drivetrain,
    canonical_engine,
    canonical_generation,
    canonical_make,
    canonical_market,
    canonical_transmission,
    compact_key,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("US", "US"),
        ("U.S.", "US"),
        ("USA", "US"),
        ("United States", "US"),
        ("United States of America", "US"),
        ("CA", "CA"),
        ("CAN", "CA"),
        ("Canada", "CA"),
    ],
)
def test_market_variants_are_canonical(raw: str, expected: str) -> None:
    assert canonical_market(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Chevy", "Chevrolet"),
        ("CHEVROLET", "Chevrolet"),
        ("vw", "Volkswagen"),
        ("Volkswagen", "Volkswagen"),
        ("ram trucks", "Ram"),
        ("gmc", "GMC"),
        ("lexus", "Lexus"),
        ("ACURA", "Acura"),
        ("Genesis", "Genesis"),
    ],
)
def test_supported_make_variants_are_canonical(raw: str, expected: str) -> None:
    assert canonical_make(raw) == expected


@pytest.mark.parametrize(
    "brand",
    [
        "BMW",
        "Audi",
        "Mercedes",
        "Mercedes-Benz",
        "Porsche",
        "Ferrari",
        "Lamborghini",
        "Land Rover",
        "Range Rover",
        "Rolls Royce",
        "Volvo",
        "Jaguar",
        "Maserati",
        "Alfa Romeo",
        "Polestar",
    ],
)
def test_excluded_european_premium_brands_are_rejected(brand: str) -> None:
    with pytest.raises(UnsupportedBrandError):
        canonical_make(brand)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sedan", "Sedan"),
        ("4 Dr Sedan", "Sedan"),
        ("4-door sedan", "Sedan"),
        ("four door sedan", "Sedan"),
        ("saloon", "Sedan"),
        ("2dr coupe", "Coupe"),
        ("5-door hatchback", "Hatchback"),
        ("station wagon", "Wagon"),
        ("sport utility vehicle", "SUV"),
        ("pickup truck", "Pickup"),
        ("cabriolet", "Convertible"),
    ],
)
def test_body_style_wording_is_canonical(raw: str, expected: str) -> None:
    assert canonical_body_style(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CVT", "CVT"),
        ("continuously variable transmission", "CVT"),
        ("automatic CVT", "CVT"),
        ("eCVT", "eCVT"),
        ("manual transmission", "Manual"),
        ("AT", "Automatic"),
        ("dual-clutch transmission", "DCT"),
    ],
)
def test_transmission_wording_is_canonical(raw: str, expected: str) -> None:
    assert canonical_transmission(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FWD", "FWD"),
        ("front wheel drive", "FWD"),
        ("rear-wheel-drive", "RWD"),
        ("all wheel drive", "AWD"),
        ("4x4", "4WD"),
        ("four wheel drive", "4WD"),
    ],
)
def test_drivetrain_wording_is_canonical(raw: str, expected: str) -> None:
    assert canonical_drivetrain(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8", "8"),
        ("8th", "8"),
        ("8th gen", "8"),
        ("eighth generation", "8"),
        ("10th generation", "10"),
    ],
)
def test_generation_wording_is_canonical(raw: str, expected: str) -> None:
    assert canonical_generation(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "1.3L I4 Hybrid",
        "hybrid inline-4 1.3 liter",
        "1.3 litre 4 cylinder hybrid",
    ],
)
def test_engine_word_order_and_notation_are_canonical(raw: str) -> None:
    assert canonical_engine(raw) == "1.3L I4 HYBRID"


def test_model_and_trim_keys_ignore_case_spacing_and_punctuation() -> None:
    assert compact_key("CR-V") == compact_key("cr v") == compact_key("CRV")
    assert compact_key("F-150") == compact_key("f 150") == compact_key("F150")
    assert compact_key("EX-L") == compact_key("ex l") == compact_key("EXL")

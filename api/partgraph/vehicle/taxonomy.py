from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

CANONICALIZATION_VERSION = 2


class VehicleIdentityError(ValueError):
    """Base error for deterministic vehicle identity processing."""


class UnsupportedMarketError(VehicleIdentityError):
    pass


class UnsupportedBrandError(VehicleIdentityError):
    pass


@dataclass(frozen=True, slots=True)
class BrandDefinition:
    name: str
    status: str
    aliases: tuple[str, ...] = ()


SUPPORTED_BRANDS: tuple[BrandDefinition, ...] = (
    BrandDefinition("Acura", "active"),
    BrandDefinition("Buick", "active"),
    BrandDefinition("Cadillac", "active"),
    BrandDefinition("Chevrolet", "active", ("Chevy",)),
    BrandDefinition("Chrysler", "active"),
    BrandDefinition("Dodge", "active"),
    BrandDefinition("Ford", "active"),
    BrandDefinition("Genesis", "active"),
    BrandDefinition("GMC", "active"),
    BrandDefinition("Honda", "active"),
    BrandDefinition("Hyundai", "active"),
    BrandDefinition("Infiniti", "active"),
    BrandDefinition("Jeep", "active"),
    BrandDefinition("Kia", "active"),
    BrandDefinition("Lexus", "active"),
    BrandDefinition("Lincoln", "active"),
    BrandDefinition("Mazda", "active"),
    BrandDefinition("Mitsubishi", "active"),
    BrandDefinition("Nissan", "active"),
    BrandDefinition("Ram", "active", ("Ram Trucks",)),
    BrandDefinition("Subaru", "active"),
    BrandDefinition("Tesla", "active"),
    BrandDefinition("Toyota", "active"),
    BrandDefinition("Volkswagen", "active", ("VW",)),
    BrandDefinition("Hummer", "legacy"),
    BrandDefinition("Mercury", "legacy"),
    BrandDefinition("Pontiac", "legacy"),
    BrandDefinition("Saturn", "legacy"),
    BrandDefinition("Scion", "legacy"),
    BrandDefinition("Suzuki", "legacy"),
)

EXCLUDED_EUROPEAN_PREMIUM_BRANDS: tuple[str, ...] = (
    "Alfa Romeo",
    "Aston Martin",
    "Audi",
    "Bentley",
    "BMW",
    "Ferrari",
    "Jaguar",
    "Lamborghini",
    "Land Rover",
    "Range Rover",
    "Lotus",
    "Maserati",
    "McLaren",
    "Mercedes-Benz",
    "MINI",
    "Polestar",
    "Porsche",
    "Rolls-Royce",
    "Volvo",
)

_MARKET_ALIASES = {
    "us": "US",
    "usa": "US",
    "unitedstates": "US",
    "unitedstatesofamerica": "US",
    "ca": "CA",
    "can": "CA",
    "canada": "CA",
}

_BODY_STYLE_ALIASES = {
    "sedan": "Sedan",
    "4drsedan": "Sedan",
    "4doorsedan": "Sedan",
    "fourdoorsedan": "Sedan",
    "saloon": "Sedan",
    "coupe": "Coupe",
    "2drcoupe": "Coupe",
    "2doorcoupe": "Coupe",
    "twodoorcoupe": "Coupe",
    "hatch": "Hatchback",
    "hatchback": "Hatchback",
    "3drhatchback": "Hatchback",
    "5drhatchback": "Hatchback",
    "3doorhatchback": "Hatchback",
    "5doorhatchback": "Hatchback",
    "wagon": "Wagon",
    "stationwagon": "Wagon",
    "estate": "Wagon",
    "suv": "SUV",
    "sportutility": "SUV",
    "sportutilityvehicle": "SUV",
    "crossover": "Crossover",
    "cuv": "Crossover",
    "pickup": "Pickup",
    "pickuptruck": "Pickup",
    "truck": "Pickup",
    "minivan": "Minivan",
    "van": "Van",
    "convertible": "Convertible",
    "cabriolet": "Convertible",
    "roadster": "Roadster",
}

_TRANSMISSION_ALIASES = {
    "cvt": "CVT",
    "continuouslyvariable": "CVT",
    "continuouslyvariabletransmission": "CVT",
    "ecvt": "eCVT",
    "electroniccvt": "eCVT",
    "manual": "Manual",
    "manualtransmission": "Manual",
    "mt": "Manual",
    "automatic": "Automatic",
    "automatictransmission": "Automatic",
    "at": "Automatic",
    "dct": "DCT",
    "dualclutch": "DCT",
    "dualclutchtransmission": "DCT",
}

_DRIVETRAIN_ALIASES = {
    "fwd": "FWD",
    "frontwheel": "FWD",
    "frontwheeldrive": "FWD",
    "rwd": "RWD",
    "rearwheel": "RWD",
    "rearwheeldrive": "RWD",
    "awd": "AWD",
    "allwheel": "AWD",
    "allwheeldrive": "AWD",
    "4wd": "4WD",
    "fourwheeldrive": "4WD",
    "4x4": "4WD",
}

_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
}

_ENGINE_DISPLACEMENT = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:l|liter|liters|litre|litres)\b",
    re.IGNORECASE,
)
_ENGINE_ARCHITECTURES = (
    (r"\b(?:inline[\s-]*3|i3|l3|3[\s-]*(?:cyl|cylinder|cylinders))\b", "I3"),
    (r"\b(?:inline[\s-]*4|i4|l4|4[\s-]*(?:cyl|cylinder|cylinders))\b", "I4"),
    (r"\b(?:inline[\s-]*5|i5|l5|5[\s-]*(?:cyl|cylinder|cylinders))\b", "I5"),
    (r"\b(?:inline[\s-]*6|i6|l6|6[\s-]*(?:cyl|cylinder|cylinders))\b", "I6"),
    (r"\bv[\s-]*6\b", "V6"),
    (r"\bv[\s-]*8\b", "V8"),
    (r"\bv[\s-]*10\b", "V10"),
    (r"\bv[\s-]*12\b", "V12"),
)
_ENGINE_ARCHITECTURE_PATTERNS = tuple(
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in _ENGINE_ARCHITECTURES
)
_ENGINE_FEATURES = (
    ("hybrid", "HYBRID"),
    ("diesel", "DIESEL"),
    ("electric", "ELECTRIC"),
    ("turbocharged", "TURBO"),
    ("turbo", "TURBO"),
    ("supercharged", "SUPERCHARGED"),
)


def words(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    characters = (
        character if character.isalnum() else " "
        for character in normalized
    )
    return " ".join("".join(characters).split())


def compact_key(value: str) -> str:
    return "".join(character for character in words(value) if character.isalnum())


def clean_display(value: str) -> str:
    return " ".join(value.strip().split())


def canonical_market(value: str) -> str:
    try:
        return _MARKET_ALIASES[compact_key(value)]
    except KeyError as exc:
        raise UnsupportedMarketError(
            "PartGraph currently supports US and Canada markets."
        ) from exc


def _build_brand_maps() -> tuple[dict[str, BrandDefinition], set[str]]:
    supported: dict[str, BrandDefinition] = {}
    for brand in SUPPORTED_BRANDS:
        for label in (brand.name, *brand.aliases):
            supported[compact_key(label)] = brand

    excluded = {
        compact_key(label)
        for label in EXCLUDED_EUROPEAN_PREMIUM_BRANDS
    }
    excluded.update({"mercedes", "benz", "landrover", "rangerover", "rollsroyce"})
    return supported, excluded


_SUPPORTED_BRAND_MAP, _EXCLUDED_BRAND_KEYS = _build_brand_maps()


def canonical_make(value: str) -> str:
    key = compact_key(value)
    if key in _EXCLUDED_BRAND_KEYS:
        raise UnsupportedBrandError(
            "This European premium brand is outside the current PartGraph scope."
        )

    brand = _SUPPORTED_BRAND_MAP.get(key)
    if brand is None:
        raise UnsupportedBrandError(
            "This brand is not in the current US/Canada PartGraph scope."
        )
    return brand.name


def supported_brand_records() -> list[dict[str, str]]:
    return [
        {"name": brand.name, "status": brand.status}
        for brand in SUPPORTED_BRANDS
    ]


def canonical_model(value: str) -> str:
    cleaned = clean_display(value)
    if not cleaned:
        raise VehicleIdentityError("model cannot be blank")
    return cleaned.upper()


def canonical_trim(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_display(value)
    return cleaned.upper() if cleaned else None


def canonical_generation(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_display(value)
    if not cleaned:
        return None

    compact = compact_key(cleaned)
    compact = re.sub(r"(?:generation|gen)$", "", compact)
    numeric = re.fullmatch(r"(\d+)(?:st|nd|rd|th)?", compact)
    if numeric:
        return numeric.group(1)

    for ordinal, number in _ORDINAL_WORDS.items():
        if compact == ordinal:
            return str(number)

    return cleaned.upper()


def canonical_body_style(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_display(value)
    if not cleaned:
        return None
    return _BODY_STYLE_ALIASES.get(compact_key(cleaned), cleaned.title())


def canonical_transmission(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_display(value)
    if not cleaned:
        return None
    key = compact_key(cleaned)

    if "ecvt" in key or "electroniccvt" in key:
        return "eCVT"
    if "cvt" in key or "continuouslyvariable" in key:
        return "CVT"
    if "dct" in key or "dualclutch" in key:
        return "DCT"

    return _TRANSMISSION_ALIASES.get(key, cleaned.upper())


def canonical_drivetrain(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_display(value)
    if not cleaned:
        return None
    return _DRIVETRAIN_ALIASES.get(compact_key(cleaned), cleaned.upper())


def canonical_engine(value: str | None) -> str | None:
    if value is None:
        return None
    raw = clean_display(value)
    if not raw:
        return None

    working = unicodedata.normalize("NFKC", raw)
    tokens: list[str] = []

    displacement = _ENGINE_DISPLACEMENT.search(working)
    if displacement:
        number = displacement.group(1).rstrip("0").rstrip(".")
        tokens.append(f"{number}L")
        working = (
            f"{working[:displacement.start()]} "
            f"{working[displacement.end():]}"
        )

    for pattern, label in _ENGINE_ARCHITECTURE_PATTERNS:
        match = pattern.search(working)
        if match:
            tokens.append(label)
            working = f"{working[:match.start()]} {working[match.end():]}"
            break

    remaining_words = words(working).split()
    consumed: set[str] = set()
    for source, label in _ENGINE_FEATURES:
        source_words = words(source).split()
        if source_words and all(word in remaining_words for word in source_words):
            if label not in tokens:
                tokens.append(label)
            consumed.update(source_words)

    ignored = {"gas", "gasoline", "petrol", "engine", "motor"}
    for word in remaining_words:
        if word not in consumed and word not in ignored:
            tokens.append(word.upper())

    deduped: list[str] = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)

    return " ".join(deduped) if deduped else raw.upper()


def comparison_key(field: str, value: str | None) -> str:
    if value is None:
        return ""
    if field == "engine":
        keys = {
            compact_key(token)
            for token in value.split()
            if compact_key(token)
        }
        return "|".join(sorted(keys))
    return compact_key(value)


def canonicalize_fields(
    *,
    year: int,
    market: str,
    make: str,
    model: str,
    generation: str | None,
    trim: str | None,
    body_style: str | None,
    engine: str | None,
    transmission: str | None,
    drivetrain: str | None,
) -> dict[str, int | str | None]:
    return {
        "year": year,
        "market": canonical_market(market),
        "make": canonical_make(make),
        "model": canonical_model(model),
        "generation": canonical_generation(generation),
        "trim": canonical_trim(trim),
        "body_style": canonical_body_style(body_style),
        "engine": canonical_engine(engine),
        "transmission": canonical_transmission(transmission),
        "drivetrain": canonical_drivetrain(drivetrain),
    }

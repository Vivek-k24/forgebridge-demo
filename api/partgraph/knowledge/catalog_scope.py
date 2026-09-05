from __future__ import annotations

US_IDENTITY_MARKET = "US"
US_IDENTITY_YEAR_MIN = 1996
US_IDENTITY_YEAR_MAX = 2027
US_IDENTITY_MAKES: tuple[str, ...] = (
    "Acura",
    "Honda",
    "Hyundai",
    "Lexus",
    "Subaru",
    "Toyota",
)


def canonical_scoped_make(value: str) -> str | None:
    normalized = value.strip().casefold()
    return next(
        (make for make in US_IDENTITY_MAKES if make.casefold() == normalized),
        None,
    )


def is_scoped_year(year: int) -> bool:
    return US_IDENTITY_YEAR_MIN <= year <= US_IDENTITY_YEAR_MAX

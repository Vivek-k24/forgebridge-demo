from datetime import date

MIN_SUPPORTED_YEAR = 1996


def max_supported_year() -> int:
    """Return the current calendar year used as PartGraph's upper vehicle boundary."""
    return date.today().year


def validate_supported_year(year: int) -> int:
    maximum = max_supported_year()
    if year < MIN_SUPPORTED_YEAR or year > maximum:
        raise ValueError(
            f"PartGraph supports model years {MIN_SUPPORTED_YEAR} through {maximum}."
        )
    return year

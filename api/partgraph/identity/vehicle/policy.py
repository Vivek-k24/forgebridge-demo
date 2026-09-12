def validate_supported_year(year: int) -> int:
    """Validate shape only; vehicle coverage comes from stored data, not source-code scope."""
    if year <= 0:
        raise ValueError("model year must be a positive integer")
    return year

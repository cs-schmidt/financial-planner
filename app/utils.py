import calendar


def days_in_year(year: int) -> int:
    """Calendar length of the given year: 365 (common years) or 366 (leap years)."""

    return 366 if calendar.isleap(year) else 365

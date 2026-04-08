"""
utils/formatters.py — Number and date formatting helpers.

These pure functions convert internal Python values into human-readable strings
suitable for display in the UI and Excel reports.
"""

from datetime import date
from typing import Union


def format_currency(value: float, decimals: int = 2) -> str:
    """
    Format *value* as an Indian-style currency string.

    Example
    -------
    >>> format_currency(1234567.89)
    '12,34,567.89'
    """
    if value is None:
        return ""
    try:
        # Split into integer and decimal parts
        rounded = round(float(value), decimals)
        negative = rounded < 0
        rounded = abs(rounded)

        int_part = int(rounded)
        dec_part = rounded - int_part

        # Indian number system: last 3 digits, then groups of 2
        s = str(int_part)
        if len(s) > 3:
            last3 = s[-3:]
            rest = s[:-3]
            # Group rest in pairs from right
            pairs = []
            while len(rest) > 2:
                pairs.insert(0, rest[-2:])
                rest = rest[:-2]
            pairs.insert(0, rest)
            s = ",".join(pairs) + "," + last3
        # else s stays as-is

        if decimals > 0:
            # f"{dec_part:.Xf}" produces e.g. "0.89"; strip the leading "0" to get ".89"
            dec_str = f"{dec_part:.{decimals}f}"[1:]
            result = s + dec_str
        else:
            result = s

        return ("-" + result) if negative else result
    except (TypeError, ValueError):
        return str(value)


def format_percentage(value: float, decimals: int = 3) -> str:
    """
    Format *value* as a percentage string.

    Example
    -------
    >>> format_percentage(25.168)
    '25.168%'
    """
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return str(value)


def parse_date(date_str: str) -> date:
    """
    Parse a DD/MM/YYYY string into a :class:`datetime.date` object.

    Raises
    ------
    ValueError
        If the string cannot be parsed.
    """
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid date format: {date_str!r} — expected DD/MM/YYYY")
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    return date(year, month, day)


def format_date(d: date) -> str:
    """
    Format a :class:`datetime.date` into DD/MM/YYYY.

    Example
    -------
    >>> format_date(date(2023, 8, 15))
    '15/08/2023'
    """
    return d.strftime("%d/%m/%Y")

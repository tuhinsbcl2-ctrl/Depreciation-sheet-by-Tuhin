"""
utils/validators.py — Input validation helpers.

All public functions return ``(is_valid: bool, error_message: str)``.
When valid, the error_message is an empty string.
"""

from datetime import date
from typing import Tuple


def validate_non_negative_number(value: str, field_name: str = "Value") -> Tuple[bool, str]:
    """
    Validate that *value* can be parsed as a non-negative float (>= 0).

    Parameters
    ----------
    value : str
        Raw string from the UI input field.
    field_name : str
        Human-readable label used in the error message.

    Returns
    -------
    (True, '')  if valid
    (False, error_message)  otherwise
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number."
    if num < 0:
        return False, f"{field_name} must be zero or a positive number."
    return True, ""


# Backward-compatible alias — callers expecting the old name continue to work.
validate_positive_number = validate_non_negative_number


def validate_positive_integer(value: str, field_name: str = "Value") -> Tuple[bool, str]:
    """
    Validate that *value* is a positive integer (> 0).

    Returns
    -------
    (True, '')  or  (False, error_message)
    """
    try:
        num = int(value)
    except (ValueError, TypeError):
        return False, f"{field_name} must be a positive whole number."
    if num <= 0:
        return False, f"{field_name} must be greater than zero."
    return True, ""


def validate_date(value: str, field_name: str = "Date") -> Tuple[bool, str]:
    """
    Validate that *value* is a date in DD/MM/YYYY format.

    Returns
    -------
    (True, '')  or  (False, error_message)
    """
    try:
        parts = value.strip().split("/")
        if len(parts) != 3:
            raise ValueError
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        date(year, month, day)  # raises ValueError if invalid calendar date
        return True, ""
    except (ValueError, AttributeError):
        return False, f"{field_name} must be in DD/MM/YYYY format (e.g. 15/08/2023)."


def validate_percentage(value: str, field_name: str = "Percentage") -> Tuple[bool, str]:
    """
    Validate that *value* is a float in the range [0, 100].

    Returns
    -------
    (True, '')  or  (False, error_message)
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid percentage."
    if not (0 <= num <= 100):
        return False, f"{field_name} must be between 0 and 100."
    return True, ""


def validate_non_negative(value: str, field_name: str = "Value") -> Tuple[bool, str]:
    """
    Validate that *value* is a float >= 0.  Alias kept for semantic clarity.

    Returns
    -------
    (True, '')  or  (False, error_message)
    """
    return validate_non_negative_number(value, field_name)

"""
models/companies_act.py — Depreciation calculations as per the Companies Act 2013.

Supports:
  * Straight Line Method (SLM)
  * Written Down Value method (WDV)
  * Pro-rata depreciation for the first financial year
  * Last-year adjustment so that closing WDV equals residual value exactly
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List

from config import FY_START_MONTH, FY_START_DAY, DAYS_IN_YEAR


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class DepreciationRow:
    """Holds the depreciation figures for a single financial year."""
    year_label: str        # e.g. "FY 2024-25"
    opening_wdv: float
    depreciation: float
    closing_wdv: float


@dataclass
class AssetInput:
    """All inputs required to compute a Companies Act depreciation schedule."""
    asset_name: str
    category: str
    cost: float
    purchase_date: date
    useful_life: int       # years
    residual_value_pct: float  # percentage, e.g. 5.0 for 5 %
    method: str            # "SLM" or "WDV"

    @property
    def residual_value(self) -> float:
        """Absolute residual value derived from cost and percentage."""
        return self.cost * self.residual_value_pct / 100.0


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _fy_start(year: int) -> date:
    """Return the start date of the financial year beginning in *year* (April 1)."""
    return date(year, FY_START_MONTH, FY_START_DAY)


def _fy_end(fy_start_year: int) -> date:
    """Return March 31 of the FY that started in *fy_start_year*."""
    return date(fy_start_year + 1, 3, 31)


def _fy_total_days(fy_start_year: int) -> int:
    """
    Return the total number of days in the financial year that starts in
    *fy_start_year* (April 1 → March 31).

    Accounts for leap years so the pro-rata denominator is always correct.
    """
    start = _fy_start(fy_start_year)
    end = _fy_end(fy_start_year)
    return (end - start).days + 1  # inclusive of both endpoints


def _days_in_fy_from_purchase(purchase_date: date) -> int:
    """
    Count how many days from *purchase_date* until the end of its financial year
    (March 31), inclusive of both endpoints.

    This is used for the pro-rata first-year depreciation.
    """
    # Determine which FY the purchase belongs to
    if purchase_date.month >= FY_START_MONTH:
        fy_start_year = purchase_date.year
    else:
        fy_start_year = purchase_date.year - 1

    fy_end_date = _fy_end(fy_start_year)
    return (fy_end_date - purchase_date).days + 1  # inclusive


def _wdv_rate(cost: float, residual_value: float, useful_life: int) -> float:
    """
    Compute the WDV depreciation rate using the formula:
        rate = 1 - (Residual Value / Cost) ^ (1 / Useful Life)

    If residual value is 0, use a very small floor to avoid log(0).
    """
    if cost <= 0:
        return 0.0
    # Guard against residual_value == 0 (would give rate == 1.0, which is valid
    # but results in the full asset being written off in year 1).
    rv = residual_value if residual_value > 0 else 0.0
    if rv <= 0:
        # Asset fully written off: use rate that reaches ~0 by end of life
        return 1 - (0.001 / cost) ** (1.0 / useful_life)
    return 1 - (rv / cost) ** (1.0 / useful_life)


# ---------------------------------------------------------------------------
# Main calculation functions
# ---------------------------------------------------------------------------

def compute_depreciation_schedule(asset: AssetInput) -> List[DepreciationRow]:
    """
    Build the complete year-by-year depreciation schedule for *asset*.

    Returns a list of :class:`DepreciationRow` objects — one per financial year
    from the year of purchase until the WDV reaches residual value.

    Pro-rata rule:
        In the first FY the depreciation is proportional to the number of days
        the asset was held within that FY  (purchase_date → March 31), divided
        by 365.

    Last-year rule:
        In the final year the depreciation is adjusted so that closing WDV
        exactly equals the residual value (preventing negative WDV).
    """
    if asset.cost <= 0:
        return []

    residual = asset.residual_value
    depreciable_amount = asset.cost - residual

    if depreciable_amount <= 0:
        # Nothing to depreciate — residual value >= cost
        return []

    method = asset.method.upper()
    if method not in ("SLM", "WDV"):
        raise ValueError(f"Unknown depreciation method: {asset.method!r}")

    # --- Determine starting FY ---
    purchase = asset.purchase_date
    if purchase.month >= FY_START_MONTH:
        first_fy_start_year = purchase.year
    else:
        first_fy_start_year = purchase.year - 1

    # --- Full-year depreciation amounts ---
    if method == "SLM":
        full_year_dep = depreciable_amount / asset.useful_life
    else:  # WDV
        rate = _wdv_rate(asset.cost, residual, asset.useful_life)

    # --- Build schedule ---
    schedule: List[DepreciationRow] = []
    opening_wdv = asset.cost
    fy_start_year = first_fy_start_year

    while opening_wdv > residual + 1e-6:
        fy_label = f"FY {fy_start_year}-{str(fy_start_year + 1)[-2:]}"

        if method == "SLM":
            year_dep = full_year_dep
        else:
            year_dep = opening_wdv * rate

        # Pro-rata adjustment for the first financial year
        if fy_start_year == first_fy_start_year:
            days_held = _days_in_fy_from_purchase(purchase)
            fy_days = _fy_total_days(first_fy_start_year)
            year_dep = year_dep * days_held / fy_days

        # Last-year adjustment: don't go below residual value
        if opening_wdv - year_dep < residual:
            year_dep = opening_wdv - residual

        year_dep = max(year_dep, 0.0)
        closing_wdv = opening_wdv - year_dep

        schedule.append(DepreciationRow(
            year_label=fy_label,
            opening_wdv=round(opening_wdv, 2),
            depreciation=round(year_dep, 2),
            closing_wdv=round(closing_wdv, 2),
        ))

        opening_wdv = closing_wdv
        fy_start_year += 1

        # Safety guard: if depreciation per year is tiny, stop after useful_life * 3
        if len(schedule) > asset.useful_life * 3 + 1:
            break

    return schedule

"""
models/income_tax.py — Depreciation under the Income Tax Act 1961.

Key rules implemented:
  * Written Down Value (WDV) method for all blocks
  * 50% depreciation if the asset was used for fewer than 180 days in the year
  * Capital-gain warning when deletions exceed opening WDV + additions
  * Closing WDV is capped at zero (depreciation cannot create a negative WDV)
"""

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class TaxBlockInput:
    """All inputs required for one Income Tax depreciation block."""
    block_name: str
    opening_wdv: float         # WDV at the start of the financial year
    additions: float           # Assets added during the year
    deletions: float           # Assets sold / deleted during the year
    rate: float                # Depreciation rate as a percentage (e.g. 15.0 for 15 %)
    less_than_180_days: bool   # True → apply 50 % of normal rate


@dataclass
class TaxDepreciationResult:
    """Result of a single Income Tax block depreciation calculation."""
    block_name: str
    opening_wdv: float
    additions: float
    deletions: float
    adjusted_wdv: float
    effective_rate: float      # Rate actually used (after 180-day rule)
    depreciation: float
    closing_wdv: float
    capital_gain_flag: bool    # True when deletions > opening WDV + additions
    capital_gain_amount: float # Absolute amount of notional capital gain (if any)


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

def compute_tax_depreciation(block: TaxBlockInput) -> TaxDepreciationResult:
    """
    Compute the Income Tax WDV depreciation for a single asset block.

    Steps
    -----
    1. Adjusted WDV  = Opening WDV + Additions − Deletions
    2. If Adjusted WDV < 0 → capital gain situation; depreciation = 0
    3. Effective rate = rate / 2  if less_than_180_days else rate
    4. Depreciation  = Adjusted WDV × (Effective Rate / 100)
    5. Closing WDV   = Adjusted WDV − Depreciation  (floored at 0)

    Parameters
    ----------
    block : TaxBlockInput
        All inputs for one depreciation block.

    Returns
    -------
    TaxDepreciationResult
        Computed figures for display and further use.
    """
    adjusted_wdv = block.opening_wdv + block.additions - block.deletions

    capital_gain_flag = False
    capital_gain_amount = 0.0

    if adjusted_wdv < 0:
        # Deletions exceeded the block value → short-term capital gain
        capital_gain_flag = True
        capital_gain_amount = abs(adjusted_wdv)
        adjusted_wdv = 0.0

    # 180-day rule: if the asset was used for less than 180 days, only half
    # of the normal depreciation rate is allowed.
    effective_rate = block.rate / 2.0 if block.less_than_180_days else block.rate

    depreciation = adjusted_wdv * (effective_rate / 100.0)

    # Closing WDV cannot be negative
    closing_wdv = max(adjusted_wdv - depreciation, 0.0)

    return TaxDepreciationResult(
        block_name=block.block_name,
        opening_wdv=round(block.opening_wdv, 2),
        additions=round(block.additions, 2),
        deletions=round(block.deletions, 2),
        adjusted_wdv=round(adjusted_wdv, 2),
        effective_rate=round(effective_rate, 3),
        depreciation=round(depreciation, 2),
        closing_wdv=round(closing_wdv, 2),
        capital_gain_flag=capital_gain_flag,
        capital_gain_amount=round(capital_gain_amount, 2),
    )

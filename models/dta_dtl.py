"""
models/dta_dtl.py — Deferred Tax Asset (DTA) and Deferred Tax Liability (DTL)
calculation as required under AS 22 / Ind AS 12.

Concept
-------
A *temporary difference* arises when the carrying value (book value) of an
asset or liability differs from its tax base (value for Income Tax purposes).

* Book Value > Tax Value  →  future taxable amount (DTL)
* Book Value < Tax Value  →  future deductible amount (DTA)
"""

from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class DtaAssetInput:
    """Inputs for a single asset's DTA/DTL computation."""
    asset_name: str
    book_value: float   # WDV per Companies Act
    tax_value: float    # WDV per Income Tax
    tax_rate: float     # Effective tax rate as a percentage (e.g. 25.168)


@dataclass
class DtaAssetResult:
    """Computed DTA/DTL figures for one asset."""
    asset_name: str
    book_value: float
    tax_value: float
    difference: float          # book_value − tax_value
    tax_rate: float
    dta: float                 # Deferred Tax Asset  (if difference < 0)
    dtl: float                 # Deferred Tax Liability (if difference > 0)


@dataclass
class DtaSummary:
    """Aggregated DTA/DTL position across all assets."""
    rows: List[DtaAssetResult]
    net_dta: float             # Positive → net asset position
    net_dtl: float             # Positive → net liability position


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

def compute_dta_dtl(assets: List[DtaAssetInput]) -> DtaSummary:
    """
    Compute DTA / DTL for a list of assets and return the summary.

    For each asset:
        difference = book_value − tax_value
        if difference > 0  →  DTL = difference × (tax_rate / 100)
        if difference < 0  →  DTA = |difference| × (tax_rate / 100)

    The summary contains the net position:
        net_dta = sum(DTA) − sum(DTL)   [positive means net asset]
        net_dtl = sum(DTL) − sum(DTA)   [positive means net liability]

    Parameters
    ----------
    assets : list of DtaAssetInput

    Returns
    -------
    DtaSummary
    """
    rows: List[DtaAssetResult] = []
    total_dta = 0.0
    total_dtl = 0.0

    for asset in assets:
        diff = asset.book_value - asset.tax_value
        tax_factor = asset.tax_rate / 100.0

        if diff > 0:
            # Book value exceeds tax value → taxable temporary difference → DTL
            dtl = diff * tax_factor
            dta = 0.0
        elif diff < 0:
            # Tax value exceeds book value → deductible temporary difference → DTA
            dta = abs(diff) * tax_factor
            dtl = 0.0
        else:
            dta = 0.0
            dtl = 0.0

        total_dta += dta
        total_dtl += dtl

        rows.append(DtaAssetResult(
            asset_name=asset.asset_name,
            book_value=round(asset.book_value, 2),
            tax_value=round(asset.tax_value, 2),
            difference=round(diff, 2),
            tax_rate=round(asset.tax_rate, 3),
            dta=round(dta, 2),
            dtl=round(dtl, 2),
        ))

    net_dta = round(max(total_dta - total_dtl, 0.0), 2)
    net_dtl = round(max(total_dtl - total_dta, 0.0), 2)

    return DtaSummary(rows=rows, net_dta=net_dta, net_dtl=net_dtl)

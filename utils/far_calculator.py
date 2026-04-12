"""
utils/far_calculator.py — Pure calculation logic for FAR bulk depreciation.

Provides asset-type mapping and the per-asset calculation function used by
the FAR Import tab.  Keeping this logic separate from the UI allows it to
be unit-tested without requiring a display (tkinter).
"""

from datetime import date
from typing import Optional

from config import (
    ASSET_CATEGORIES,
    COMPANIES_ACT_USEFUL_LIVES,
    CA_TO_IT_BLOCK_MAP,
    DEFAULT_RESIDUAL_VALUE_PCT,
    DEFAULT_PURCHASE_LOOKBACK_YEARS,
    FAR_ASSET_TYPE_TO_CA_CATEGORY,
)
from models.companies_act import AssetInput, compute_depreciation_schedule
from models.income_tax import TaxBlockInput, compute_tax_depreciation
from models.dta_dtl import DtaAssetInput, compute_dta_dtl
from utils.formatters import parse_date


# ---------------------------------------------------------------------------
# Category / block helpers
# ---------------------------------------------------------------------------

def asset_type_to_ca_category(asset_type: str) -> str:
    """
    Map a free-text *asset_type* string from the FAR to one of the canonical
    Companies Act categories defined in ASSET_CATEGORIES.

    Performs a case-insensitive substring search against
    FAR_ASSET_TYPE_TO_CA_CATEGORY.  Falls back to the first ASSET_CATEGORIES
    entry if no match is found.
    """
    lower = asset_type.lower()
    for keyword, category in FAR_ASSET_TYPE_TO_CA_CATEGORY:
        if keyword in lower:
            return category
    return ASSET_CATEGORIES[0]


def ca_category_to_it_block(ca_category: str) -> str:
    """Return the IT block name for a given CA category."""
    return CA_TO_IT_BLOCK_MAP.get(ca_category, list(CA_TO_IT_BLOCK_MAP.values())[0])


# ---------------------------------------------------------------------------
# Per-asset calculation
# ---------------------------------------------------------------------------

def calculate_asset(row: dict, fy_label: str, tax_rate: float) -> dict:
    """
    Compute IT depreciation, CA depreciation, and DTA/DTL for a single FAR row.

    Parameters
    ----------
    row       : FAR row dict (from import_far_data)
    fy_label  : e.g. "FY 2025-26"
    tax_rate  : effective tax rate as a percentage (e.g. 25.168)

    Returns
    -------
    dict with keys:
        asset_id, asset_name, asset_type,
        it_opening_wdv, it_depreciation, it_closing_wdv,
        ca_opening_wdv, ca_depreciation, ca_closing_wdv,
        difference, tax_rate,
        opening_dta, opening_dtl, dta, dtl,
        it_capital_gain, it_capital_gain_amount
    """
    asset_name  = row.get("asset_name", "")
    asset_type  = row.get("asset_type", "")
    cost        = row.get("cost", 0.0)
    opening_wdv = row.get("opening_wdv", 0.0)
    additions   = row.get("additions", 0.0)
    deletions   = row.get("deletions", 0.0)
    dep_rate    = row.get("dep_rate", 0.0)
    days_used   = row.get("days_used", 365.0)
    dep_method  = row.get("dep_method", "WDV").upper()
    opening_dta = row.get("opening_dta", 0.0)
    opening_dtl = row.get("opening_dtl", 0.0)

    # ── Income Tax depreciation ─────────────────────────────────────────────
    ca_category = asset_type_to_ca_category(asset_type)
    it_block_input = TaxBlockInput(
        block_name=ca_category_to_it_block(ca_category),
        opening_wdv=opening_wdv,
        additions=additions,
        deletions=deletions,
        rate=dep_rate,
        less_than_180_days=(days_used < 180),
    )
    it_result = compute_tax_depreciation(it_block_input)

    # ── Companies Act depreciation ──────────────────────────────────────────
    useful_life = COMPANIES_ACT_USEFUL_LIVES.get(ca_category, 10)
    method = dep_method if dep_method in ("SLM", "WDV") else "WDV"

    # Determine purchase / put-to-use date
    raw_date = row.get("put_to_use_date") or row.get("purchase_date")
    try:
        pdate: Optional[date] = parse_date(raw_date) if raw_date else None
    except Exception:
        pdate = None
    if pdate is None:
        pdate = date(date.today().year - DEFAULT_PURCHASE_LOOKBACK_YEARS, 4, 1)

    ca_depreciation = 0.0
    ca_opening_wdv  = opening_wdv   # default if schedule has no matching row
    ca_closing_wdv  = opening_wdv

    if cost > 0:
        ca_asset = AssetInput(
            asset_name=asset_name,
            category=ca_category,
            cost=cost,
            purchase_date=pdate,
            useful_life=useful_life,
            residual_value_pct=DEFAULT_RESIDUAL_VALUE_PCT,
            method=method,
        )
        schedule = compute_depreciation_schedule(ca_asset)
        ca_row = next((r for r in schedule if r.year_label == fy_label), None)

        if ca_row is not None:
            ca_opening_wdv  = ca_row.opening_wdv
            ca_depreciation = ca_row.depreciation
            ca_closing_wdv  = ca_row.closing_wdv
        elif schedule:
            # The FY is beyond the useful life — asset fully depreciated
            last = schedule[-1]
            ca_opening_wdv  = last.closing_wdv
            ca_depreciation = 0.0
            ca_closing_wdv  = last.closing_wdv
    else:
        # No cost provided — derive simple depreciation from opening WDV × rate
        residual_val = opening_wdv * (DEFAULT_RESIDUAL_VALUE_PCT / 100.0)
        if dep_method == "SLM":
            ca_depreciation = (opening_wdv - residual_val) / max(useful_life, 1)
        else:
            ca_depreciation = opening_wdv * (dep_rate / 100.0)
        ca_depreciation = min(ca_depreciation, max(opening_wdv - residual_val, 0.0))
        ca_closing_wdv  = opening_wdv - ca_depreciation

    # ── DTA / DTL ───────────────────────────────────────────────────────────
    # The closing DTA/DTL for this year is computed from the current-year
    # closing WDVs, then adjusted by the opening DTA/DTL carried forward.
    dta_input = DtaAssetInput(
        asset_name=asset_name,
        book_value=ca_closing_wdv,
        tax_value=it_result.closing_wdv,
        tax_rate=tax_rate,
    )
    dta_summary = compute_dta_dtl([dta_input])
    dta_row = dta_summary.rows[0] if dta_summary.rows else None

    # Apply opening DTA/DTL balances to arrive at the closing (net) position:
    #
    # The current-year gross DTA/DTL is first computed purely from closing WDVs.
    # The opening balance from the prior year is then incorporated as follows:
    #
    #   closing_dta = current_dta + opening_dta − opening_dtl
    #   closing_dtl = current_dtl + opening_dtl − opening_dta
    #
    # Rationale: A prior-year DTA (deferred tax asset) adds to the current DTA
    # balance and offsets any DTL.  A prior-year DTL works in the opposite
    # direction.  This mirrors how deferred tax balances are rolled forward in
    # double-entry accounting (the opening balance plus the current-year movement
    # equals the closing balance), consistent with AS 22 / IND AS 12 treatment
    # of temporary differences and deferred tax roll-forward.
    current_dta = round(dta_row.dta, 2) if dta_row else 0.0
    current_dtl = round(dta_row.dtl, 2) if dta_row else 0.0
    closing_dta = max(round(current_dta + opening_dta - opening_dtl, 2), 0.0)
    closing_dtl = max(round(current_dtl + opening_dtl - opening_dta, 2), 0.0)
    # Ensure only one of DTA/DTL is non-zero (they are mutually exclusive per asset)
    if closing_dta > 0 and closing_dtl > 0:
        net = closing_dta - closing_dtl
        closing_dta = max(net, 0.0)
        closing_dtl = max(-net, 0.0)

    return {
        "asset_id":               row.get("asset_id", ""),
        "asset_name":             asset_name,
        "asset_type":             asset_type,
        "it_opening_wdv":         it_result.opening_wdv,
        "it_depreciation":        it_result.depreciation,
        "it_closing_wdv":         it_result.closing_wdv,
        "ca_opening_wdv":         round(ca_opening_wdv, 2),
        "ca_depreciation":        round(ca_depreciation, 2),
        "ca_closing_wdv":         round(ca_closing_wdv, 2),
        "difference":             round(dta_row.difference, 2) if dta_row else 0.0,
        "tax_rate":               tax_rate,
        "opening_dta":            round(opening_dta, 2),
        "opening_dtl":            round(opening_dtl, 2),
        "dta":                    closing_dta,
        "dtl":                    closing_dtl,
        "it_capital_gain":        it_result.capital_gain_flag,
        "it_capital_gain_amount": it_result.capital_gain_amount,
    }

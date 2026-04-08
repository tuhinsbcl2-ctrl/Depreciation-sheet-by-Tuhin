"""
tests/test_companies_act.py — Unit tests for Companies Act depreciation logic.

Covers:
  * SLM full-year depreciation
  * WDV full-year depreciation
  * Pro-rata first-year depreciation
  * Last-year adjustment (closing WDV = residual value)
  * Edge cases: zero cost, 100% residual value
"""

import unittest
from datetime import date

from models.companies_act import (
    AssetInput,
    compute_depreciation_schedule,
    _days_in_fy_from_purchase,
    _wdv_rate,
)


class TestDaysInFY(unittest.TestCase):
    """Tests for the pro-rata day-count helper."""

    def test_purchased_on_april_1(self):
        """Asset purchased on FY start — should use full FY days (365 or 366)."""
        from models.companies_act import _fy_total_days
        days = _days_in_fy_from_purchase(date(2023, 4, 1))
        # Should equal the total days in FY 2023-24 (which includes leap day Feb 29)
        expected = _fy_total_days(2023)
        self.assertEqual(days, expected)

    def test_purchased_on_march_31(self):
        """Asset purchased on the last day of FY — only 1 day."""
        days = _days_in_fy_from_purchase(date(2024, 3, 31))
        self.assertEqual(days, 1)

    def test_purchased_mid_year(self):
        """October 1 → March 31: 182 days (incl. both endpoints)."""
        days = _days_in_fy_from_purchase(date(2023, 10, 1))
        expected = (date(2024, 3, 31) - date(2023, 10, 1)).days + 1
        self.assertEqual(days, expected)

    def test_purchased_in_jan(self):
        """January purchase falls in same FY (Jan is within the Apr–Mar year)."""
        days = _days_in_fy_from_purchase(date(2024, 1, 15))
        expected = (date(2024, 3, 31) - date(2024, 1, 15)).days + 1
        self.assertEqual(days, expected)


class TestSLMDepreciation(unittest.TestCase):
    """Tests for Straight-Line Method (SLM)."""

    def _make_asset(self, cost=100000, life=10, residual_pct=5.0,
                    purchase_date=date(2022, 4, 1)):
        return AssetInput(
            asset_name="Test Asset",
            category="Building",
            cost=cost,
            purchase_date=purchase_date,
            useful_life=life,
            residual_value_pct=residual_pct,
            method="SLM",
        )

    def test_full_year_depreciation_amount(self):
        """SLM: full-year purchase (Apr 1) gives exactly one full-year depreciation."""
        asset = self._make_asset(cost=100000, life=10, residual_pct=5.0)
        schedule = compute_depreciation_schedule(asset)
        expected_annual = (100000 - 5000) / 10   # = 9500
        # First row is full-year (purchased Apr 1 → days_held == fy_total_days)
        # So pro-rata = 1.0 and depreciation == full year amount
        self.assertAlmostEqual(schedule[0].depreciation, expected_annual, places=1)

    def test_number_of_years(self):
        """SLM schedule should have exactly *useful_life* rows for Apr 1 purchase."""
        asset = self._make_asset(cost=100000, life=5, residual_pct=5.0)
        schedule = compute_depreciation_schedule(asset)
        self.assertEqual(len(schedule), 5)

    def test_closing_wdv_last_year(self):
        """Last year closing WDV must equal the residual value."""
        asset = self._make_asset(cost=100000, life=5, residual_pct=5.0)
        schedule = compute_depreciation_schedule(asset)
        self.assertAlmostEqual(schedule[-1].closing_wdv, 5000.0, places=1)

    def test_opening_wdv_equals_previous_closing(self):
        """Each year's opening WDV should match the previous year's closing WDV."""
        asset = self._make_asset(cost=100000, life=5, residual_pct=5.0)
        schedule = compute_depreciation_schedule(asset)
        for i in range(1, len(schedule)):
            self.assertAlmostEqual(
                schedule[i].opening_wdv, schedule[i - 1].closing_wdv, places=2
            )

    def test_pro_rata_first_year(self):
        """Pro-rata: purchase on Oct 1 gives partial first year depreciation."""
        asset = self._make_asset(
            cost=100000, life=10, residual_pct=5.0,
            purchase_date=date(2022, 10, 1),
        )
        from models.companies_act import _fy_total_days
        full_year_dep = (100000 - 5000) / 10  # 9500
        fy_start_year = 2022
        days = (date(2023, 3, 31) - date(2022, 10, 1)).days + 1
        fy_days = _fy_total_days(fy_start_year)
        expected_pro_rata = full_year_dep * days / fy_days
        schedule = compute_depreciation_schedule(asset)
        self.assertAlmostEqual(schedule[0].depreciation, expected_pro_rata, places=1)

    def test_zero_cost_returns_empty(self):
        """Zero cost asset should return an empty schedule."""
        asset = self._make_asset(cost=0)
        schedule = compute_depreciation_schedule(asset)
        self.assertEqual(schedule, [])

    def test_residual_equals_cost_returns_empty(self):
        """If residual value >= cost, nothing to depreciate."""
        asset = self._make_asset(cost=100000, residual_pct=100.0)
        schedule = compute_depreciation_schedule(asset)
        self.assertEqual(schedule, [])


class TestWDVDepreciation(unittest.TestCase):
    """Tests for Written-Down Value (WDV) method."""

    def _make_asset(self, cost=100000, life=5, residual_pct=5.0,
                    purchase_date=date(2022, 4, 1)):
        return AssetInput(
            asset_name="Test Asset",
            category="Plant & Machinery",
            cost=cost,
            purchase_date=purchase_date,
            useful_life=life,
            residual_value_pct=residual_pct,
            method="WDV",
        )

    def test_rate_calculation(self):
        """WDV rate = 1 - (RV/Cost)^(1/life)."""
        rate = _wdv_rate(100000, 5000, 5)
        expected = 1 - (5000 / 100000) ** (1 / 5)
        self.assertAlmostEqual(rate, expected, places=8)

    def test_closing_wdv_last_year(self):
        """WDV closing WDV in last year must not exceed residual value."""
        asset = self._make_asset(cost=100000, life=5, residual_pct=5.0)
        schedule = compute_depreciation_schedule(asset)
        self.assertAlmostEqual(schedule[-1].closing_wdv, 5000.0, places=0)

    def test_depreciation_decreasing(self):
        """WDV depreciation amounts should be non-increasing over the schedule."""
        asset = self._make_asset(cost=100000, life=5, residual_pct=5.0)
        schedule = compute_depreciation_schedule(asset)
        deps = [r.depreciation for r in schedule[:-1]]  # exclude last (adjusted)
        for i in range(1, len(deps)):
            self.assertLessEqual(deps[i], deps[i - 1] + 0.01)  # allow rounding

    def test_pro_rata_first_year_wdv(self):
        """WDV pro-rata: depreciation in first partial year < full-year amount."""
        asset_full = self._make_asset(purchase_date=date(2022, 4, 1))
        asset_part = self._make_asset(purchase_date=date(2022, 10, 1))
        full_schedule = compute_depreciation_schedule(asset_full)
        part_schedule = compute_depreciation_schedule(asset_part)
        self.assertLess(part_schedule[0].depreciation, full_schedule[0].depreciation)

    def test_opening_matches_previous_closing(self):
        """Every opening WDV should match the previous year's closing WDV."""
        asset = self._make_asset()
        schedule = compute_depreciation_schedule(asset)
        for i in range(1, len(schedule)):
            self.assertAlmostEqual(
                schedule[i].opening_wdv, schedule[i - 1].closing_wdv, places=2
            )


if __name__ == "__main__":
    unittest.main()

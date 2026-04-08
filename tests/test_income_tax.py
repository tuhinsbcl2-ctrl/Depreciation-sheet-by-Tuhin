"""
tests/test_income_tax.py — Unit tests for Income Tax depreciation logic.

Covers:
  * Normal full-rate depreciation
  * 180-day rule (50% rate)
  * Capital gain when deletions exceed adjusted WDV
  * Zero opening WDV
  * Closing WDV never goes negative
"""

import unittest

from models.income_tax import TaxBlockInput, compute_tax_depreciation


class TestNormalDepreciation(unittest.TestCase):
    """Standard WDV depreciation without special conditions."""

    def test_basic_depreciation(self):
        """Rate 15% on 100,000 should give depreciation = 15,000."""
        block = TaxBlockInput(
            block_name="Plant & Machinery (General)",
            opening_wdv=100000.0,
            additions=0.0,
            deletions=0.0,
            rate=15.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.depreciation, 15000.0, places=2)
        self.assertAlmostEqual(result.closing_wdv, 85000.0, places=2)

    def test_additions_increase_adjusted_wdv(self):
        """Additions are included in the base for depreciation."""
        block = TaxBlockInput(
            block_name="Plant & Machinery (General)",
            opening_wdv=80000.0,
            additions=20000.0,
            deletions=0.0,
            rate=15.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.adjusted_wdv, 100000.0, places=2)
        self.assertAlmostEqual(result.depreciation, 15000.0, places=2)

    def test_deletions_reduce_adjusted_wdv(self):
        """Deletions reduce the base before applying the rate."""
        block = TaxBlockInput(
            block_name="Building (Residential)",
            opening_wdv=100000.0,
            additions=0.0,
            deletions=10000.0,
            rate=10.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.adjusted_wdv, 90000.0, places=2)
        self.assertAlmostEqual(result.depreciation, 9000.0, places=2)


class Test180DayRule(unittest.TestCase):
    """Depreciation capped at 50% of normal rate for assets used < 180 days."""

    def test_half_rate_applied(self):
        """15% rate should become 7.5% when less_than_180_days is True."""
        block = TaxBlockInput(
            block_name="Plant & Machinery (General)",
            opening_wdv=100000.0,
            additions=0.0,
            deletions=0.0,
            rate=15.0,
            less_than_180_days=True,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.effective_rate, 7.5, places=3)
        self.assertAlmostEqual(result.depreciation, 7500.0, places=2)

    def test_full_rate_without_180_day_flag(self):
        """Normal rate used when less_than_180_days is False."""
        block = TaxBlockInput(
            block_name="Plant & Machinery (General)",
            opening_wdv=100000.0,
            additions=0.0,
            deletions=0.0,
            rate=15.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.effective_rate, 15.0, places=3)


class TestCapitalGain(unittest.TestCase):
    """Tests for the capital gain scenario when deletions exceed block value."""

    def test_capital_gain_flag(self):
        """When deletions > opening WDV + additions, capital_gain_flag must be True."""
        block = TaxBlockInput(
            block_name="Building (Residential)",
            opening_wdv=50000.0,
            additions=0.0,
            deletions=60000.0,
            rate=10.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertTrue(result.capital_gain_flag)

    def test_capital_gain_amount(self):
        """Capital gain amount = |adjusted_wdv| before zeroing it."""
        block = TaxBlockInput(
            block_name="Building (Residential)",
            opening_wdv=50000.0,
            additions=0.0,
            deletions=60000.0,
            rate=10.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.capital_gain_amount, 10000.0, places=2)

    def test_depreciation_zero_on_capital_gain(self):
        """Depreciation must be 0 when a capital gain arises."""
        block = TaxBlockInput(
            block_name="Building (Residential)",
            opening_wdv=50000.0,
            additions=0.0,
            deletions=60000.0,
            rate=10.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.depreciation, 0.0, places=2)

    def test_closing_wdv_zero_on_capital_gain(self):
        """Closing WDV must be 0 (not negative) when capital gain arises."""
        block = TaxBlockInput(
            block_name="Building (Residential)",
            opening_wdv=50000.0,
            additions=0.0,
            deletions=60000.0,
            rate=10.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.closing_wdv, 0.0, places=2)


class TestEdgeCases(unittest.TestCase):
    """Edge case tests for Income Tax depreciation."""

    def test_zero_opening_wdv_and_additions(self):
        """Zero base means zero depreciation and zero closing WDV."""
        block = TaxBlockInput(
            block_name="Furniture & Fittings",
            opening_wdv=0.0,
            additions=0.0,
            deletions=0.0,
            rate=10.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.depreciation, 0.0, places=2)
        self.assertAlmostEqual(result.closing_wdv, 0.0, places=2)

    def test_zero_rate(self):
        """0% rate should yield zero depreciation."""
        block = TaxBlockInput(
            block_name="Building (Residential)",
            opening_wdv=100000.0,
            additions=0.0,
            deletions=0.0,
            rate=0.0,
            less_than_180_days=False,
        )
        result = compute_tax_depreciation(block)
        self.assertAlmostEqual(result.depreciation, 0.0, places=2)
        self.assertAlmostEqual(result.closing_wdv, 100000.0, places=2)


if __name__ == "__main__":
    unittest.main()

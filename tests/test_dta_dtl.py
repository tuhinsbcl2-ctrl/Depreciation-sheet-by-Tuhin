"""
tests/test_dta_dtl.py — Unit tests for DTA / DTL calculation logic.

Covers:
  * DTL when book value > tax value
  * DTA when book value < tax value
  * No difference (zero DTA and DTL)
  * Multiple assets — net position calculation
  * Net DTA vs Net DTL selection
  * Opening balance and movement calculations
"""

import unittest

from models.dta_dtl import DtaAssetInput, compute_dta_dtl


class TestSingleAsset(unittest.TestCase):
    """DTA / DTL for a single asset."""

    def test_dtl_when_book_greater_than_tax(self):
        """Book value > Tax value → DTL."""
        assets = [DtaAssetInput("Machine A", book_value=80000, tax_value=60000, tax_rate=25.0)]
        summary = compute_dta_dtl(assets)
        self.assertEqual(len(summary.rows), 1)
        row = summary.rows[0]
        # Difference = 80000 - 60000 = 20000
        self.assertAlmostEqual(row.difference, 20000.0, places=2)
        self.assertAlmostEqual(row.dtl, 5000.0, places=2)   # 20000 * 25%
        self.assertAlmostEqual(row.dta, 0.0, places=2)
        # Default opening balance = 0; closing = 0 - 5000 = -5000 (DTL)
        self.assertAlmostEqual(row.opening_balance, 0.0, places=2)
        self.assertAlmostEqual(row.closing_balance, -5000.0, places=2)
        self.assertAlmostEqual(row.movement, -5000.0, places=2)

    def test_dta_when_tax_greater_than_book(self):
        """Tax value > Book value → DTA."""
        assets = [DtaAssetInput("Machine B", book_value=40000, tax_value=60000, tax_rate=25.0)]
        summary = compute_dta_dtl(assets)
        row = summary.rows[0]
        self.assertAlmostEqual(row.difference, -20000.0, places=2)
        self.assertAlmostEqual(row.dta, 5000.0, places=2)   # 20000 * 25%
        self.assertAlmostEqual(row.dtl, 0.0, places=2)

    def test_no_difference(self):
        """Equal values → zero DTA and DTL."""
        assets = [DtaAssetInput("Building C", book_value=50000, tax_value=50000, tax_rate=30.0)]
        summary = compute_dta_dtl(assets)
        row = summary.rows[0]
        self.assertAlmostEqual(row.dta, 0.0, places=2)
        self.assertAlmostEqual(row.dtl, 0.0, places=2)


class TestMultipleAssets(unittest.TestCase):
    """Net DTA / DTL across multiple assets."""

    def test_net_dtl(self):
        """When total DTL > total DTA, net_dtl should be positive and net_dta = 0."""
        assets = [
            DtaAssetInput("Asset 1", book_value=100000, tax_value=70000, tax_rate=25.0),  # DTL 7500
            DtaAssetInput("Asset 2", book_value=50000,  tax_value=55000, tax_rate=25.0),  # DTA 1250
        ]
        summary = compute_dta_dtl(assets)
        # Net DTL = 7500 - 1250 = 6250
        self.assertAlmostEqual(summary.net_dtl, 6250.0, places=2)
        self.assertAlmostEqual(summary.net_dta, 0.0, places=2)

    def test_net_dta(self):
        """When total DTA > total DTL, net_dta should be positive and net_dtl = 0."""
        assets = [
            DtaAssetInput("Asset 1", book_value=40000,  tax_value=80000, tax_rate=25.0),  # DTA 10000
            DtaAssetInput("Asset 2", book_value=100000, tax_value=90000, tax_rate=25.0),  # DTL 2500
        ]
        summary = compute_dta_dtl(assets)
        # Net DTA = 10000 - 2500 = 7500
        self.assertAlmostEqual(summary.net_dta, 7500.0, places=2)
        self.assertAlmostEqual(summary.net_dtl, 0.0, places=2)

    def test_empty_list(self):
        """Empty asset list should return zero net DTA and DTL."""
        summary = compute_dta_dtl([])
        self.assertAlmostEqual(summary.net_dta, 0.0, places=2)
        self.assertAlmostEqual(summary.net_dtl, 0.0, places=2)
        self.assertEqual(len(summary.rows), 0)

    def test_tax_rate_applied_correctly(self):
        """Different tax rates should be used per asset."""
        assets = [
            DtaAssetInput("High Rate", book_value=100000, tax_value=50000, tax_rate=34.944),
            DtaAssetInput("Low Rate",  book_value=100000, tax_value=50000, tax_rate=25.168),
        ]
        summary = compute_dta_dtl(assets)
        # DTL for first  = 50000 * 34.944% = 17472.0
        # DTL for second = 50000 * 25.168% = 12584.0
        # Both are DTL so net_dtl = 17472 + 12584 = 30056
        expected_net_dtl = 50000 * 0.34944 + 50000 * 0.25168
        self.assertAlmostEqual(summary.net_dtl, round(expected_net_dtl, 2), places=1)


class TestEdgeCases(unittest.TestCase):
    """Edge cases for DTA/DTL computation."""

    def test_zero_book_and_tax_value(self):
        """Both zero → no tax effect."""
        assets = [DtaAssetInput("Zero Asset", book_value=0.0, tax_value=0.0, tax_rate=25.0)]
        summary = compute_dta_dtl(assets)
        self.assertAlmostEqual(summary.net_dta, 0.0, places=2)
        self.assertAlmostEqual(summary.net_dtl, 0.0, places=2)

    def test_zero_tax_rate(self):
        """0% tax rate → DTA and DTL are zero even with a difference."""
        assets = [DtaAssetInput("No Tax", book_value=100000, tax_value=50000, tax_rate=0.0)]
        summary = compute_dta_dtl(assets)
        self.assertAlmostEqual(summary.rows[0].dtl, 0.0, places=2)
        self.assertAlmostEqual(summary.rows[0].dta, 0.0, places=2)


class TestOpeningBalanceAndMovement(unittest.TestCase):
    """Tests for opening balance, movement, and closing balance logic."""

    def test_opening_balance_default_zero(self):
        """Default opening_balance should be 0.0 and movement equals closing."""
        assets = [DtaAssetInput("A", book_value=60000, tax_value=80000, tax_rate=25.0)]
        summary = compute_dta_dtl(assets)
        row = summary.rows[0]
        # DTA = (80000 - 60000) * 25% = 5000; closing = +5000
        self.assertAlmostEqual(row.opening_balance, 0.0, places=2)
        self.assertAlmostEqual(row.closing_balance, 5000.0, places=2)
        self.assertAlmostEqual(row.movement, 5000.0, places=2)

    def test_opening_balance_dta_reduces_movement(self):
        """When there is a prior DTA opening balance, movement is smaller."""
        # Prior year DTA = 3000, current year DTA = 5000; movement = 2000
        assets = [DtaAssetInput("A", book_value=60000, tax_value=80000,
                                 tax_rate=25.0, opening_balance=3000.0)]
        summary = compute_dta_dtl(assets)
        row = summary.rows[0]
        self.assertAlmostEqual(row.opening_balance, 3000.0, places=2)
        self.assertAlmostEqual(row.closing_balance, 5000.0, places=2)
        self.assertAlmostEqual(row.movement, 2000.0, places=2)

    def test_opening_dtl_balance_reversal(self):
        """Prior DTL opening balance (negative) reverses when current year is DTA."""
        # Prior year DTL = 2000 → opening = -2000; current DTA = 5000
        # movement = 5000 - (-2000) = 7000
        assets = [DtaAssetInput("A", book_value=60000, tax_value=80000,
                                 tax_rate=25.0, opening_balance=-2000.0)]
        summary = compute_dta_dtl(assets)
        row = summary.rows[0]
        self.assertAlmostEqual(row.opening_balance, -2000.0, places=2)
        self.assertAlmostEqual(row.closing_balance, 5000.0, places=2)
        self.assertAlmostEqual(row.movement, 7000.0, places=2)

    def test_summary_total_opening_balance(self):
        """total_opening_balance should be the signed sum across all assets."""
        assets = [
            DtaAssetInput("A", book_value=40000, tax_value=60000,
                           tax_rate=25.0, opening_balance=2000.0),   # DTA opening
            DtaAssetInput("B", book_value=80000, tax_value=60000,
                           tax_rate=25.0, opening_balance=-1000.0),  # DTL opening
        ]
        summary = compute_dta_dtl(assets)
        # total_opening = 2000 + (-1000) = 1000
        self.assertAlmostEqual(summary.total_opening_balance, 1000.0, places=2)

    def test_summary_net_closing_balance(self):
        """net_closing_balance = net DTA − net DTL (signed)."""
        assets = [DtaAssetInput("A", book_value=40000, tax_value=60000, tax_rate=25.0)]
        summary = compute_dta_dtl(assets)
        # DTA = 20000 * 25% = 5000 → net_closing = +5000
        self.assertAlmostEqual(summary.net_closing_balance, 5000.0, places=2)

    def test_summary_net_movement(self):
        """net_movement = net_closing_balance − total_opening_balance."""
        assets = [DtaAssetInput("A", book_value=40000, tax_value=60000,
                                 tax_rate=25.0, opening_balance=3000.0)]
        summary = compute_dta_dtl(assets)
        # closing = 5000, opening = 3000; movement = 2000
        self.assertAlmostEqual(summary.net_movement, 2000.0, places=2)


class TestGenerateFYOptions(unittest.TestCase):
    """Tests for the FY option generator in config."""

    def test_current_fy_in_options(self):
        """The default FY should be present in the options list."""
        from config import generate_fy_options
        options, current_fy = generate_fy_options()
        self.assertIn(current_fy, options)

    def test_fy_format(self):
        """Every FY string should match 'FY YYYY-YY' pattern."""
        from config import generate_fy_options
        import re
        options, _ = generate_fy_options()
        pattern = re.compile(r"^FY \d{4}-\d{2}$")
        for fy in options:
            self.assertRegex(fy, pattern)

    def test_options_are_consecutive(self):
        """Each FY should be exactly one year after the previous."""
        from config import generate_fy_options
        options, _ = generate_fy_options()
        for i in range(1, len(options)):
            prev_year = int(options[i - 1].split()[1].split("-")[0])
            curr_year = int(options[i].split()[1].split("-")[0])
            self.assertEqual(curr_year, prev_year + 1)


if __name__ == "__main__":
    unittest.main()

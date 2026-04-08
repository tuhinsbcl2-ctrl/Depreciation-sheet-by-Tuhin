"""
tests/test_dta_dtl.py — Unit tests for DTA / DTL calculation logic.

Covers:
  * DTL when book value > tax value
  * DTA when book value < tax value
  * No difference (zero DTA and DTL)
  * Multiple assets — net position calculation
  * Net DTA vs Net DTL selection
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


if __name__ == "__main__":
    unittest.main()

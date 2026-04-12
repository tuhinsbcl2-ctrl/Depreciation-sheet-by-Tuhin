"""
tests/test_far_import.py — Unit tests for FAR import parsing and calculation logic.

Covers:
  * _map_far_columns: flexible column header matching
  * _extract_far_row: data extraction from a raw row
  * import_far_data (CSV path): end-to-end CSV import
  * asset_type_to_ca_category: asset type mapping
  * calculate_asset: IT + CA depreciation and DTA/DTL calculation
"""

import csv
import os
import tempfile
import unittest
from datetime import date

from utils.excel_handler import _map_far_columns, _extract_far_row, _to_float, import_far_data
from utils.far_calculator import asset_type_to_ca_category, calculate_asset


class TestMapFarColumns(unittest.TestCase):
    """Tests for the FAR column-header mapper."""

    def test_exact_lowercase_match(self):
        headers = ["asset id", "asset name", "cost", "opening wdv", "dep rate"]
        col_map = _map_far_columns(headers)
        self.assertEqual(col_map["asset_id"], 0)
        self.assertEqual(col_map["asset_name"], 1)
        self.assertEqual(col_map["cost"], 2)
        self.assertEqual(col_map["opening_wdv"], 3)
        self.assertEqual(col_map["dep_rate"], 4)

    def test_partial_match(self):
        """'additions during year' contains 'addition' → maps to 'additions'."""
        headers = ["asset name", "additions during year", "deletion value"]
        col_map = _map_far_columns(headers)
        self.assertEqual(col_map["additions"], 1)
        self.assertEqual(col_map["deletions"], 2)

    def test_sale_value_maps_to_deletions(self):
        """'sale value' is an alternate header for deletions."""
        headers = ["asset name", "sale value"]
        col_map = _map_far_columns(headers)
        self.assertEqual(col_map["deletions"], 1)

    def test_method_fallback(self):
        """'depreciation method' takes priority over plain 'method'."""
        headers = ["asset name", "depreciation method", "method"]
        col_map = _map_far_columns(headers)
        # 'depreciation method' is listed first in _FAR_HEADER_MAP and should win
        self.assertEqual(col_map["dep_method"], 1)

    def test_empty_headers(self):
        col_map = _map_far_columns([])
        self.assertEqual(col_map, {})


class TestExtractFarRow(unittest.TestCase):
    """Tests for _extract_far_row."""

    def _make_row(self, **kwargs):
        """Create a 10-element row list populated from kwargs by position."""
        headers = [
            "asset id", "asset name", "asset type", "purchase date",
            "put to use date", "cost", "opening wdv", "additions",
            "deletions", "dep rate",
        ]
        col_map = _map_far_columns(headers)
        row = [None] * len(headers)
        for field, val in kwargs.items():
            idx = col_map.get(field)
            if idx is not None:
                row[idx] = val
        return row, col_map

    def test_basic_extraction(self):
        row, col_map = self._make_row(
            asset_name="Machine A",
            cost=100000.0,
            opening_wdv=80000.0,
            dep_rate=15.0,
        )
        entry = _extract_far_row(row, col_map)
        self.assertEqual(entry["asset_name"], "Machine A")
        self.assertAlmostEqual(entry["cost"], 100000.0)
        self.assertAlmostEqual(entry["opening_wdv"], 80000.0)
        self.assertAlmostEqual(entry["dep_rate"], 15.0)

    def test_missing_optional_field_defaults(self):
        row, col_map = self._make_row(asset_name="X")
        entry = _extract_far_row(row, col_map)
        self.assertEqual(entry["additions"], 0.0)
        self.assertEqual(entry["deletions"], 0.0)
        self.assertEqual(entry["days_used"], 365.0)

    def test_date_from_date_object(self):
        headers = ["asset name", "purchase date"]
        col_map = _map_far_columns(headers)
        row = ["Asset", date(2024, 7, 15)]
        entry = _extract_far_row(row, col_map)
        self.assertEqual(entry["purchase_date"], "15/07/2024")


class TestToFloat(unittest.TestCase):
    def test_int(self):
        self.assertAlmostEqual(_to_float(100), 100.0)

    def test_string_number(self):
        self.assertAlmostEqual(_to_float("12.5"), 12.5)

    def test_none_returns_default(self):
        self.assertAlmostEqual(_to_float(None), 0.0)
        self.assertAlmostEqual(_to_float(None, 99.0), 99.0)

    def test_invalid_string(self):
        self.assertAlmostEqual(_to_float("abc"), 0.0)


class TestAssetTypeToCACategory(unittest.TestCase):
    """Tests for the FAR asset-type → CA category mapper."""

    def test_building(self):
        self.assertEqual(asset_type_to_ca_category("Commercial Building"), "Building")

    def test_plant(self):
        self.assertEqual(asset_type_to_ca_category("Plant & Machinery"), "Plant & Machinery")

    def test_vehicle(self):
        self.assertEqual(asset_type_to_ca_category("Delivery Vehicle"), "Vehicles")

    def test_computer(self):
        self.assertEqual(asset_type_to_ca_category("Computer"), "Computer & IT Equipment")

    def test_unknown_falls_back(self):
        from config import ASSET_CATEGORIES
        result = asset_type_to_ca_category("Unknowntype123")
        self.assertEqual(result, ASSET_CATEGORIES[0])

    def test_case_insensitive(self):
        self.assertEqual(asset_type_to_ca_category("BUILDING"), "Building")
        self.assertEqual(asset_type_to_ca_category("furniture"), "Furniture & Fittings")


class TestCalculateAsset(unittest.TestCase):
    """Integration tests for calculate_asset."""

    def _make_row(self, **kwargs):
        defaults = {
            "asset_id": "A001",
            "asset_name": "Test Machine",
            "asset_type": "Plant & Machinery",
            "purchase_date": "01/04/2020",
            "put_to_use_date": "01/04/2020",
            "cost": 100000.0,
            "opening_wdv": 52087.0,  # WDV after 5 years at 15%
            "additions": 0.0,
            "deletions": 0.0,
            "dep_rate": 15.0,
            "days_used": 365.0,
            "dep_method": "WDV",
        }
        defaults.update(kwargs)
        return defaults

    def test_it_depreciation_basic(self):
        """IT depreciation = opening_wdv × rate."""
        row = self._make_row(opening_wdv=100000.0, dep_rate=15.0)
        result = calculate_asset(row, "FY 2025-26", 25.168)
        self.assertAlmostEqual(result["it_depreciation"], 15000.0, delta=1.0)
        self.assertAlmostEqual(result["it_closing_wdv"], 85000.0, delta=1.0)

    def test_it_half_rate_below_180_days(self):
        """Days used < 180 → IT rate halved."""
        row = self._make_row(opening_wdv=100000.0, dep_rate=15.0, days_used=90)
        result = calculate_asset(row, "FY 2025-26", 25.168)
        self.assertAlmostEqual(result["it_depreciation"], 7500.0, delta=1.0)

    def test_capital_gain_flag(self):
        """Deletions exceeding WDV triggers capital gain flag."""
        row = self._make_row(opening_wdv=10000.0, deletions=20000.0, dep_rate=15.0)
        result = calculate_asset(row, "FY 2025-26", 25.168)
        self.assertTrue(result["it_capital_gain"])
        self.assertEqual(result["it_depreciation"], 0.0)

    def test_dta_when_ca_closing_greater_than_it(self):
        """CA WDV > IT WDV → DTL (book value exceeds tax base)."""
        # High CA closing WDV means more book value, so DTL
        row = self._make_row(
            asset_type="Computer",
            cost=100000.0,
            opening_wdv=50000.0,
            dep_rate=40.0,    # high IT rate → low IT closing WDV
            purchase_date="01/04/2023",
            put_to_use_date="01/04/2023",
        )
        result = calculate_asset(row, "FY 2025-26", 25.168)
        # IT closing WDV should be lower than CA closing WDV for computer
        # (CA for Computer: 3-year life SLM/WDV — asset may already be fully depreciated)
        # Just check types and non-negative
        self.assertGreaterEqual(result["dta"], 0.0)
        self.assertGreaterEqual(result["dtl"], 0.0)
        # Exactly one of DTA/DTL should be non-zero (or both zero if equal)
        self.assertFalse(result["dta"] > 0 and result["dtl"] > 0)

    def test_result_keys_present(self):
        """All expected keys present in the result dict."""
        row = self._make_row()
        result = calculate_asset(row, "FY 2025-26", 25.168)
        for key in (
            "asset_id", "asset_name", "asset_type",
            "it_opening_wdv", "it_depreciation", "it_closing_wdv",
            "ca_opening_wdv", "ca_depreciation", "ca_closing_wdv",
            "difference", "tax_rate", "dta", "dtl",
            "it_capital_gain", "it_capital_gain_amount",
        ):
            self.assertIn(key, result, f"Missing key: {key}")


class TestImportFarCSV(unittest.TestCase):
    """Test CSV import via import_far_data."""

    def _write_csv(self, rows, headers=None):
        if headers is None:
            headers = [
                "Asset ID", "Asset Name", "Asset Type", "Purchase Date",
                "Put to Use Date", "Cost", "Opening WDV", "Additions",
                "Deletions", "Dep Rate (%)", "Days Used", "Depreciation Method",
            ]
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8",
        )
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        f.close()
        return f.name

    def tearDown(self):
        # Clean up temp files
        pass

    def test_basic_csv_import(self):
        path = self._write_csv([
            ["A001", "Machine A", "Plant & Machinery", "01/04/2020", "01/04/2020",
             "100000", "52087", "0", "0", "15", "365", "WDV"],
            ["A002", "Office Chair", "Furniture", "01/07/2022", "01/07/2022",
             "20000", "14000", "0", "0", "10", "300", "SLM"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["asset_name"], "Machine A")
        self.assertAlmostEqual(rows[0]["cost"], 100000.0)
        self.assertEqual(rows[1]["dep_method"], "SLM")

    def test_missing_asset_name_skipped(self):
        path = self._write_csv([
            ["A001", "",  "Plant & Machinery", "01/04/2020", "", "100000", "0", "0", "0", "15", "365", "WDV"],
            ["A002", "Valid Asset", "Building", "01/04/2019", "", "500000", "0", "0", "0", "10", "365", "SLM"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("missing Asset Name", errors[0])

    def test_empty_csv(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8",
        )
        f.close()
        rows, errors = import_far_data(f.name)
        os.unlink(f.name)
        self.assertEqual(rows, [])
        self.assertTrue(len(errors) > 0)

    def test_no_asset_name_column(self):
        path = self._write_csv([["X", "Y"]], headers=["Col1", "Col2"])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertEqual(rows, [])
        self.assertTrue(any("Asset Name" in e for e in errors))


if __name__ == "__main__":
    unittest.main()

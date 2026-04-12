"""
tests/test_new_features.py — Tests for new features:
  * FAR import validation (pandas path)
  * Opening DTA/DTL in calculate_asset
  * AppSettings load/save
  * AssetDatabase save/load/rollover
"""

import csv
import os
import tempfile
import unittest

from utils.excel_handler import import_far_data, _validate_far_entry, PANDAS_AVAILABLE
from utils.far_calculator import calculate_asset


class TestFARValidation(unittest.TestCase):
    """Tests for pandas-backed FAR import with row validation."""

    def _write_csv(self, rows, headers=None):
        if headers is None:
            headers = [
                "Asset ID", "Asset Name", "Asset Type", "Purchase Date",
                "Cost", "Opening WDV", "Dep Rate (%)", "Days Used",
                "Depreciation Method", "Opening DTA", "Opening DTL",
            ]
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8",
        )
        try:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        finally:
            f.close()
        return f.name

    def test_valid_rows_imported(self):
        path = self._write_csv([
            ["A001", "Machine", "Plant & Machinery", "01/04/2020",
             "100000", "50000", "15", "365", "WDV", "0", "0"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_name"], "Machine")

    def test_opening_dta_dtl_parsed(self):
        path = self._write_csv([
            ["A001", "Machine", "Plant & Machinery", "01/04/2020",
             "100000", "50000", "15", "365", "WDV", "2500", "0"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["opening_dta"], 2500.0)
        self.assertAlmostEqual(rows[0]["opening_dtl"], 0.0)

    @unittest.skipUnless(PANDAS_AVAILABLE, "pandas not installed")
    def test_bad_numeric_produces_error(self):
        path = self._write_csv([
            ["A001", "Machine", "Plant & Machinery", "01/04/2020",
             "BAD_COST", "50000", "15", "365", "WDV", "0", "0"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        # Row is kept but error is reported
        self.assertTrue(any("BAD_COST" in e for e in errors), f"No error found: {errors}")

    @unittest.skipUnless(PANDAS_AVAILABLE, "pandas not installed")
    def test_bad_date_produces_error(self):
        path = self._write_csv([
            ["A001", "Machine", "Plant & Machinery", "NOT-A-DATE",
             "100000", "50000", "15", "365", "WDV", "0", "0"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertTrue(any("invalid date" in e.lower() for e in errors), f"No error found: {errors}")

    def test_missing_asset_name_skipped_and_errors_reported(self):
        path = self._write_csv([
            ["A001", "", "Plant & Machinery", "01/04/2020",
             "100000", "50000", "15", "365", "WDV", "0", "0"],
            ["A002", "Valid Asset", "Building", "01/04/2020",
             "500000", "300000", "10", "365", "SLM", "0", "0"],
        ])
        rows, errors = import_far_data(path)
        os.unlink(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asset_name"], "Valid Asset")
        self.assertTrue(len(errors) >= 1)


class TestValidateFarEntry(unittest.TestCase):
    """Unit tests for _validate_far_entry."""

    def _base_entry(self, **kwargs):
        entry = {
            "asset_name": "Test Asset",
            "cost": 100000.0,
            "opening_wdv": 50000.0,
            "dep_rate": 15.0,
            "days_used": 365.0,
            "additions": 0.0,
            "deletions": 0.0,
            "purchase_date": "01/04/2020",
            "put_to_use_date": None,
            "sale_date": None,
            "opening_dta": 0.0,
            "opening_dtl": 0.0,
        }
        entry.update(kwargs)
        return entry

    def test_valid_entry_no_errors(self):
        entry = self._base_entry()
        issues = _validate_far_entry(entry, 2)
        self.assertEqual(issues, [])

    def test_missing_asset_name(self):
        entry = self._base_entry(asset_name="")
        issues = _validate_far_entry(entry, 2)
        self.assertTrue(any("missing Asset Name" in i for i in issues))

    def test_invalid_date_in_entry(self):
        entry = self._base_entry(purchase_date="32/13/2020")
        issues = _validate_far_entry(entry, 2)
        self.assertTrue(any("invalid date" in i.lower() for i in issues))

    def test_raw_row_numeric_validation(self):
        """When raw_row is provided, text in a numeric column is caught."""
        from utils.excel_handler import _map_far_columns
        headers = ["asset name", "cost", "opening wdv"]
        col_map = _map_far_columns(headers)
        raw_row = ["Test Asset", "NOT_A_NUMBER", "50000"]
        entry = self._base_entry()
        issues = _validate_far_entry(entry, 2, raw_row=raw_row, col_map=col_map)
        self.assertTrue(any("NOT_A_NUMBER" in i for i in issues), f"Issues: {issues}")


class TestCalculateAssetWithOpeningDTADTL(unittest.TestCase):
    """Tests for calculate_asset with opening DTA/DTL."""

    def _make_row(self, **kwargs):
        defaults = {
            "asset_id": "A001",
            "asset_name": "Test Machine",
            "asset_type": "Plant & Machinery",
            "purchase_date": "01/04/2020",
            "put_to_use_date": "01/04/2020",
            "cost": 100000.0,
            "opening_wdv": 52087.0,
            "additions": 0.0,
            "deletions": 0.0,
            "dep_rate": 15.0,
            "days_used": 365.0,
            "dep_method": "WDV",
            "opening_dta": 0.0,
            "opening_dtl": 0.0,
        }
        defaults.update(kwargs)
        return defaults

    def test_opening_dta_included_in_result(self):
        row = self._make_row(opening_dta=1000.0, opening_dtl=0.0)
        result = calculate_asset(row, "FY 2025-26", 25.168)
        self.assertIn("opening_dta", result)
        self.assertIn("opening_dtl", result)
        self.assertAlmostEqual(result["opening_dta"], 1000.0)
        self.assertAlmostEqual(result["opening_dtl"], 0.0)

    def test_opening_dta_adds_to_closing_dta(self):
        """Opening DTA should increase closing DTA."""
        row_no_open = self._make_row(opening_dta=0.0)
        row_with_open = self._make_row(opening_dta=5000.0)
        result_no = calculate_asset(row_no_open, "FY 2025-26", 25.168)
        result_with = calculate_asset(row_with_open, "FY 2025-26", 25.168)
        # Closing DTA with opening balance should be >= without
        self.assertGreaterEqual(result_with["dta"], result_no["dta"])

    def test_zero_opening_balances_unchanged(self):
        """Zero opening balances should not change the calculation."""
        row = self._make_row(opening_dta=0.0, opening_dtl=0.0)
        result = calculate_asset(row, "FY 2025-26", 25.168)
        self.assertGreaterEqual(result["dta"], 0.0)
        self.assertGreaterEqual(result["dtl"], 0.0)

    def test_result_has_new_keys(self):
        """Ensure opening_dta and opening_dtl are present in the result."""
        row = self._make_row()
        result = calculate_asset(row, "FY 2025-26", 25.168)
        self.assertIn("opening_dta", result)
        self.assertIn("opening_dtl", result)


class TestAppSettings(unittest.TestCase):
    """Tests for AppSettings load/save."""

    def setUp(self):
        self._tmp_fh = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp = self._tmp_fh.name
        self._tmp_fh.close()
        # Remove the file so AppSettings sees a missing file and creates defaults
        os.unlink(self._tmp)

    def tearDown(self):
        if os.path.exists(self._tmp):
            os.unlink(self._tmp)

    def test_defaults_created_when_no_file(self):
        from utils.app_settings import AppSettings
        s = AppSettings(path=self._tmp)
        self.assertIsInstance(s.useful_lives, dict)
        self.assertIn("Building", s.useful_lives)
        self.assertIsInstance(s.it_rates, dict)

    def test_save_and_reload(self):
        from utils.app_settings import AppSettings
        s = AppSettings(path=self._tmp)
        s.useful_lives = {"Building": 99}
        s.save()

        s2 = AppSettings(path=self._tmp)
        self.assertEqual(s2.useful_lives.get("Building"), 99)

    def test_invalid_json_uses_defaults(self):
        with open(self._tmp, "w") as f:
            f.write("NOT JSON")
        from utils.app_settings import AppSettings
        s = AppSettings(path=self._tmp)
        self.assertIsInstance(s.useful_lives, dict)


class TestAssetDatabase(unittest.TestCase):
    """Tests for AssetDatabase."""

    def setUp(self):
        fh = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_db = fh.name
        fh.close()
        os.unlink(self._tmp_db)  # Let SQLite create a fresh file

    def tearDown(self):
        if os.path.exists(self._tmp_db):
            os.unlink(self._tmp_db)

    def _make_results(self, n=2):
        results = []
        for i in range(1, n + 1):
            results.append({
                "asset_id": f"A{i:03d}",
                "asset_name": f"Asset {i}",
                "asset_type": "Plant & Machinery",
                "it_opening_wdv": 100000.0,
                "it_depreciation": 15000.0,
                "it_closing_wdv": 85000.0,
                "it_capital_gain": False,
                "it_capital_gain_amount": 0.0,
                "ca_opening_wdv": 100000.0,
                "ca_depreciation": 10000.0,
                "ca_closing_wdv": 90000.0,
                "difference": 5000.0,
                "tax_rate": 25.168,
                "opening_dta": 0.0,
                "opening_dtl": 0.0,
                "dta": 1258.4,
                "dtl": 0.0,
            })
        return results

    def test_save_and_load(self):
        from utils.database import AssetDatabase
        db = AssetDatabase(path=self._tmp_db)
        results = self._make_results(3)
        n = db.save_far_results("FY 2025-26", results)
        self.assertEqual(n, 3)

        loaded = db.get_history("FY 2025-26")
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded[0]["asset_id"], "A001")

    def test_list_financial_years(self):
        from utils.database import AssetDatabase
        db = AssetDatabase(path=self._tmp_db)
        db.save_far_results("FY 2024-25", self._make_results(1))
        db.save_far_results("FY 2025-26", self._make_results(2))
        fys = db.list_financial_years()
        self.assertIn("FY 2024-25", fys)
        self.assertIn("FY 2025-26", fys)

    def test_rollover(self):
        from utils.database import AssetDatabase
        db = AssetDatabase(path=self._tmp_db)
        results = self._make_results(2)
        db.save_far_results("FY 2025-26", results)
        rolled = db.rollover_year("FY 2025-26", "FY 2026-27")
        self.assertEqual(len(rolled), 2)
        # Opening WDV for rollover = IT closing WDV of previous year
        self.assertAlmostEqual(rolled[0]["opening_wdv"], 85000.0)
        # Opening DTA = previous year closing DTA
        self.assertAlmostEqual(rolled[0]["opening_dta"], 1258.4)

    def test_rollover_empty_source(self):
        from utils.database import AssetDatabase
        db = AssetDatabase(path=self._tmp_db)
        rolled = db.rollover_year("FY 2099-00", "FY 2100-01")
        self.assertEqual(rolled, [])

    def test_delete_fy(self):
        from utils.database import AssetDatabase
        db = AssetDatabase(path=self._tmp_db)
        db.save_far_results("FY 2025-26", self._make_results(2))
        n = db.delete_fy("FY 2025-26")
        self.assertEqual(n, 2)
        loaded = db.get_history("FY 2025-26")
        self.assertEqual(loaded, [])

    def test_upsert_replaces_existing(self):
        from utils.database import AssetDatabase
        db = AssetDatabase(path=self._tmp_db)
        results = self._make_results(1)
        db.save_far_results("FY 2025-26", results)
        # Save again with different values — should replace
        results[0]["it_depreciation"] = 20000.0
        db.save_far_results("FY 2025-26", results)
        loaded = db.get_history("FY 2025-26")
        self.assertEqual(len(loaded), 1)
        self.assertAlmostEqual(loaded[0]["it_depreciation"], 20000.0)


if __name__ == "__main__":
    unittest.main()

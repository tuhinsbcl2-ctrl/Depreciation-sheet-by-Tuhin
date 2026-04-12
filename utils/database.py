"""
utils/database.py — SQLite persistence for the Fixed Asset Register.

The database is stored in ``far_history.db`` in the same directory as the
executable / repository root.

Schema
------
``assets``
    Master asset table. One row per physical asset.

``far_records``
    One row per (asset, financial year).  The Closing WDV of year N becomes
    the Opening WDV of year N+1 (handled by ``rollover_year``).

Public API
----------
    from utils.database import db
    db.save_far_results("FY 2025-26", results)   # list[dict] from calculate_asset
    rows = db.get_history("FY 2025-26")
    all_fys = db.list_financial_years()
    db.rollover_year("FY 2025-26", "FY 2026-27")
"""

import logging
import os
import sqlite3
import sys
from contextlib import contextmanager
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB location
# ---------------------------------------------------------------------------

def _db_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_DB_PATH = os.path.join(_db_dir(), "far_history.db")

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS assets (
    asset_id    TEXT PRIMARY KEY,
    asset_name  TEXT NOT NULL,
    asset_type  TEXT
);

CREATE TABLE IF NOT EXISTS far_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    financial_year   TEXT    NOT NULL,
    asset_id         TEXT    NOT NULL,
    asset_name       TEXT,
    asset_type       TEXT,

    -- Income Tax columns
    it_opening_wdv   REAL    DEFAULT 0,
    it_depreciation  REAL    DEFAULT 0,
    it_closing_wdv   REAL    DEFAULT 0,
    it_capital_gain  INTEGER DEFAULT 0,
    it_capital_gain_amount REAL DEFAULT 0,

    -- Companies Act columns
    ca_opening_wdv   REAL    DEFAULT 0,
    ca_depreciation  REAL    DEFAULT 0,
    ca_closing_wdv   REAL    DEFAULT 0,

    -- DTA / DTL
    difference       REAL    DEFAULT 0,
    tax_rate         REAL    DEFAULT 0,
    opening_dta      REAL    DEFAULT 0,
    opening_dtl      REAL    DEFAULT 0,
    dta              REAL    DEFAULT 0,
    dtl              REAL    DEFAULT 0,

    saved_at         TEXT    DEFAULT (datetime('now')),
    UNIQUE (financial_year, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_far_fy ON far_records (financial_year);
"""

# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------

class AssetDatabase:
    """Thin wrapper around a SQLite connection for FAR history storage."""

    def __init__(self, path: str = _DB_PATH):
        self._path = path
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        """Yield a database connection, committing on success or rolling back on error."""
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        try:
            with self._conn() as conn:
                conn.executescript(_DDL)
            log.info("Database initialised at %s", self._path)
        except Exception as exc:
            log.error("Database init failed: %s", exc)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_far_results(self, financial_year: str, results: List[dict]) -> int:
        """
        Persist a list of calculate_asset result dicts for the given FY.

        Existing records for the same (financial_year, asset_id) are replaced.

        Returns
        -------
        int — number of rows written.
        """
        if not results:
            return 0

        sql = """
            INSERT OR REPLACE INTO far_records (
                financial_year, asset_id, asset_name, asset_type,
                it_opening_wdv, it_depreciation, it_closing_wdv,
                it_capital_gain, it_capital_gain_amount,
                ca_opening_wdv, ca_depreciation, ca_closing_wdv,
                difference, tax_rate,
                opening_dta, opening_dtl, dta, dtl
            ) VALUES (
                :financial_year, :asset_id, :asset_name, :asset_type,
                :it_opening_wdv, :it_depreciation, :it_closing_wdv,
                :it_capital_gain, :it_capital_gain_amount,
                :ca_opening_wdv, :ca_depreciation, :ca_closing_wdv,
                :difference, :tax_rate,
                :opening_dta, :opening_dtl, :dta, :dtl
            )
        """
        rows_data = []
        for r in results:
            rows_data.append({
                "financial_year":        financial_year,
                "asset_id":              r.get("asset_id", ""),
                "asset_name":            r.get("asset_name", ""),
                "asset_type":            r.get("asset_type", ""),
                "it_opening_wdv":        r.get("it_opening_wdv", 0.0),
                "it_depreciation":       r.get("it_depreciation", 0.0),
                "it_closing_wdv":        r.get("it_closing_wdv", 0.0),
                "it_capital_gain":       int(r.get("it_capital_gain", False)),
                "it_capital_gain_amount":r.get("it_capital_gain_amount", 0.0),
                "ca_opening_wdv":        r.get("ca_opening_wdv", 0.0),
                "ca_depreciation":       r.get("ca_depreciation", 0.0),
                "ca_closing_wdv":        r.get("ca_closing_wdv", 0.0),
                "difference":            r.get("difference", 0.0),
                "tax_rate":              r.get("tax_rate", 0.0),
                "opening_dta":           r.get("opening_dta", 0.0),
                "opening_dtl":           r.get("opening_dtl", 0.0),
                "dta":                   r.get("dta", 0.0),
                "dtl":                   r.get("dtl", 0.0),
            })

        with self._conn() as conn:
            conn.executemany(sql, rows_data)

        log.info("Saved %d FAR records for %s", len(results), financial_year)
        return len(results)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_history(self, financial_year: Optional[str] = None) -> List[dict]:
        """
        Return all FAR records, optionally filtered by *financial_year*.
        Each record is returned as a plain dict.
        """
        with self._conn() as conn:
            if financial_year:
                cur = conn.execute(
                    "SELECT * FROM far_records WHERE financial_year = ? ORDER BY asset_id",
                    (financial_year,),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM far_records ORDER BY financial_year, asset_id"
                )
            return [dict(row) for row in cur.fetchall()]

    def list_financial_years(self) -> List[str]:
        """Return a sorted list of financial years that have saved records."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT DISTINCT financial_year FROM far_records ORDER BY financial_year"
            )
            return [row[0] for row in cur.fetchall()]

    def delete_fy(self, financial_year: str) -> int:
        """Delete all records for *financial_year*.  Returns rows deleted."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM far_records WHERE financial_year = ?", (financial_year,)
            )
            return cur.rowcount

    # ------------------------------------------------------------------
    # Year roll-over
    # ------------------------------------------------------------------

    def rollover_year(self, from_fy: str, to_fy: str) -> List[dict]:
        """
        Create opening rows for *to_fy* from the closing WDV of *from_fy*.

        * ``opening_wdv`` for IT in *to_fy* ← ``it_closing_wdv`` of *from_fy*
        * ``opening_wdv`` for CA in *to_fy* ← ``ca_closing_wdv`` of *from_fy*
        * ``opening_dta``  in *to_fy* ← ``dta`` of *from_fy*
        * ``opening_dtl``  in *to_fy* ← ``dtl`` of *from_fy*

        Returns
        -------
        List[dict] — the rolled-over rows (pre-calculation, ready for import).
        """
        source = self.get_history(from_fy)
        if not source:
            log.warning("No records for %s — nothing to roll over.", from_fy)
            return []

        rolled: List[dict] = []
        for r in source:
            rolled.append({
                "asset_id":       r["asset_id"],
                "asset_name":     r["asset_name"],
                "asset_type":     r["asset_type"],
                "opening_wdv":    r["it_closing_wdv"],   # IT opening WDV
                "ca_opening_wdv": r["ca_closing_wdv"],
                "opening_dta":    r["dta"],
                "opening_dtl":    r["dtl"],
                # Reset current-year fields
                "cost":         0.0,
                "additions":    0.0,
                "deletions":    0.0,
                "dep_rate":     0.0,
                "days_used":    365.0,
                "dep_method":   "WDV",
                "purchase_date":    None,
                "put_to_use_date":  None,
            })
        log.info(
            "Rolled over %d assets from %s to %s", len(rolled), from_fy, to_fy
        )
        return rolled


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

db = AssetDatabase()

"""
utils/app_settings.py — Persistent application settings (JSON-backed).

Settings are stored in ``settings.json`` in the same directory as the
executable / repository root.  If the file does not exist the built-in
defaults from ``config.py`` are used and the file is created automatically.

Public API
----------
    from utils.app_settings import AppSettings
    settings = AppSettings()          # loads or creates settings.json
    lives = settings.useful_lives     # dict: category → years
    rates = settings.it_rates         # dict: block → %
    settings.useful_lives["Building"] = 25
    settings.save()                   # persist changes

The ``AppSettings`` singleton can also be imported directly:
    from utils.app_settings import settings
"""

import json
import logging
import os
import sys
from typing import Dict

from config import (
    COMPANIES_ACT_USEFUL_LIVES,
    INCOME_TAX_BLOCKS,
    DTA_DTL_TAX_RATES,
    DEFAULT_RESIDUAL_VALUE_PCT,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Locate the settings file
# ---------------------------------------------------------------------------

def _settings_dir() -> str:
    """Return the directory where ``settings.json`` should live."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SETTINGS_PATH = os.path.join(_settings_dir(), "settings.json")


# ---------------------------------------------------------------------------
# Default values (sourced from config.py so they stay in sync)
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "companies_act_useful_lives": dict(COMPANIES_ACT_USEFUL_LIVES),
    "income_tax_rates": dict(INCOME_TAX_BLOCKS),
    "dta_dtl_tax_rates": {k: v for k, v in DTA_DTL_TAX_RATES.items()},
    "default_residual_value_pct": DEFAULT_RESIDUAL_VALUE_PCT,
}


# ---------------------------------------------------------------------------
# AppSettings class
# ---------------------------------------------------------------------------

class AppSettings:
    """
    Load, expose, and persist application settings from ``settings.json``.

    Attributes
    ----------
    useful_lives : dict
        Mapping of CA category → useful life in years.
    it_rates : dict
        Mapping of IT block name → depreciation rate (%).
    dta_tax_rates : dict
        Mapping of display label → effective tax rate (%).
    residual_value_pct : float
        Default residual value percentage for CA depreciation.
    """

    def __init__(self, path: str = _SETTINGS_PATH):
        self._path = path
        self._data: dict = {}
        self.load()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load settings from disk, creating the file with defaults if absent."""
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                # Merge with defaults so newly added keys are always present
                self._data = {**_DEFAULTS, **loaded}
                log.info("Settings loaded from %s", self._path)
                return
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Cannot read settings file (%s); using defaults.", exc)

        # No file or parse error — use defaults and persist them
        self._data = dict(_DEFAULTS)
        self.save()

    def save(self) -> bool:
        """Persist the current settings to ``settings.json``.  Returns True on success."""
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            log.info("Settings saved to %s", self._path)
            return True
        except OSError as exc:
            log.error("Cannot write settings file: %s", exc)
            return False

    def reload(self) -> None:
        """Re-read the settings file from disk."""
        self.load()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def useful_lives(self) -> Dict[str, int]:
        return self._data.setdefault("companies_act_useful_lives", dict(COMPANIES_ACT_USEFUL_LIVES))

    @useful_lives.setter
    def useful_lives(self, value: Dict[str, int]) -> None:
        self._data["companies_act_useful_lives"] = value

    @property
    def it_rates(self) -> Dict[str, float]:
        return self._data.setdefault("income_tax_rates", dict(INCOME_TAX_BLOCKS))

    @it_rates.setter
    def it_rates(self, value: Dict[str, float]) -> None:
        self._data["income_tax_rates"] = value

    @property
    def dta_tax_rates(self) -> Dict[str, float]:
        return self._data.setdefault("dta_dtl_tax_rates", {k: v for k, v in DTA_DTL_TAX_RATES.items()})

    @dta_tax_rates.setter
    def dta_tax_rates(self, value: Dict[str, float]) -> None:
        self._data["dta_dtl_tax_rates"] = value

    @property
    def residual_value_pct(self) -> float:
        return float(self._data.get("default_residual_value_pct", DEFAULT_RESIDUAL_VALUE_PCT))

    @residual_value_pct.setter
    def residual_value_pct(self, value: float) -> None:
        self._data["default_residual_value_pct"] = float(value)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

settings = AppSettings()

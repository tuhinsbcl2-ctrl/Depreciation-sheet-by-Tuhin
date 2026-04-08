"""
config.py — Application-wide constants for the Depreciation & DTA/DTL Calculator.

All business-rule constants (useful lives, depreciation rates, tax rates, etc.)
are centralised here so that no magic numbers appear elsewhere in the codebase.
"""

# ---------------------------------------------------------------------------
# Companies Act — Schedule II default useful lives (in years)
# Source: Companies Act 2013, Schedule II
# ---------------------------------------------------------------------------
COMPANIES_ACT_USEFUL_LIVES = {
    "Building": 30,
    "Plant & Machinery": 15,
    "Furniture & Fittings": 10,
    "Vehicles": 8,
    "Computer & IT Equipment": 3,
    "Intangible Assets": 10,
}

# Default residual value as a percentage of original cost (Companies Act)
DEFAULT_RESIDUAL_VALUE_PCT = 5.0  # 5 %

# Asset categories available in the Companies Act tab (same keys as above)
ASSET_CATEGORIES = list(COMPANIES_ACT_USEFUL_LIVES.keys())

# Depreciation methods supported under the Companies Act
DEPRECIATION_METHODS = ["SLM", "WDV"]

# ---------------------------------------------------------------------------
# Income Tax Act — Block-wise WDV depreciation rates (in %)
# Source: Income Tax Act 1961, Schedule to Appendix I
# ---------------------------------------------------------------------------
INCOME_TAX_BLOCKS = {
    "Building (Residential)": 10,
    "Building (Non-residential/Factory)": 40,
    "Plant & Machinery (General)": 15,
    "Plant & Machinery (Special)": 30,
    "Furniture & Fittings": 10,
    "Intangible Assets": 25,
}

# ---------------------------------------------------------------------------
# Deferred Tax — applicable tax rates (effective rates inclusive of
# surcharge and health & education cess as commonly used in India)
# ---------------------------------------------------------------------------
DTA_DTL_TAX_RATES = {
    "25.168% (Domestic – Sec 115BAA)": 25.168,
    "34.944% (Domestic – General)": 34.944,
}

# ---------------------------------------------------------------------------
# Financial year conventions (India: April 1 – March 31)
# ---------------------------------------------------------------------------
FY_START_MONTH = 4   # April
FY_START_DAY = 1
FY_END_MONTH = 3     # March
FY_END_DAY = 31

# Days in a standard year used for pro-rata calculation
DAYS_IN_YEAR = 365

# ---------------------------------------------------------------------------
# UI / display constants
# ---------------------------------------------------------------------------
APP_TITLE = "Depreciation & DTA Calculator — Indian Companies Act & IT Act"
MIN_WINDOW_WIDTH = 1000
MIN_WINDOW_HEIGHT = 700

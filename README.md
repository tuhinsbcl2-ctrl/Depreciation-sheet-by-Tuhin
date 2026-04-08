# Depreciation & DTA/DTL Calculator — Indian Companies Act & IT Act

A **Python desktop application** built with `tkinter` for calculating asset
depreciation under the **Indian Companies Act 2013 (Schedule II)** and
**Income Tax Act 1961**, along with **Deferred Tax Asset / Liability (DTA/DTL)**
computation as per AS 22 / Ind AS 12.

---

## Features

### Companies Act Depreciation
- Straight Line Method (SLM) and Written Down Value (WDV)
- Pro-rata depreciation for the first financial year
- Auto-populated useful lives per Schedule II asset categories
- Configurable residual value (default 5%)
- Complete year-wise depreciation schedule table

### Income Tax Depreciation
- Block-wise WDV method
- 180-day rule (50% depreciation for assets used < 180 days)
- Capital gain detection when deletions exceed block value
- Pre-configured block rates (Building 10%/40%, Plant 15%/30%, etc.)

### DTA / DTL Calculator
- Per-asset deferred tax computation
- Supports effective tax rates: 25.168% and 34.944% (plus custom entry)
- Net DTA / Net DTL summary across all assets
- Colour-coded DTA (green) and DTL (red) display

### Excel Import / Export
- Import asset register from `.xlsx` with automatic field mapping
- Export reports to Excel with headers, borders, and Indian number formatting
- All three report types on separate sheets in one workbook

---

## Installation

```bash
pip install -r requirements.txt
```

> Python 3.8+ is required. `tkinter` ships with the standard library.

---

## How to Run

```bash
python main.py
```

---

## File Structure

```
Depreciation-sheet-by-Tuhin/
├── main.py                        # Entry point
├── requirements.txt               # openpyxl dependency
├── config.py                      # All constants (rates, lives, categories)
├── models/
│   ├── companies_act.py           # SLM + WDV depreciation logic
│   ├── income_tax.py              # IT block-wise WDV logic
│   └── dta_dtl.py                 # DTA/DTL computation
├── ui/
│   ├── app.py                     # Main window + Notebook
│   ├── companies_act_tab.py       # Tab 1 — Companies Act
│   ├── income_tax_tab.py          # Tab 2 — Tax Depreciation
│   ├── dta_tab.py                 # Tab 3 — DTA/DTL
│   └── styles.py                  # Colours, fonts, padding
├── utils/
│   ├── validators.py              # Input validation helpers
│   ├── formatters.py              # Number/date formatting
│   └── excel_handler.py           # openpyxl import/export
└── tests/
    ├── test_companies_act.py
    ├── test_income_tax.py
    └── test_dta_dtl.py
```

---

## Running Tests

```bash
python -m pytest tests/
```

or with the standard library runner:

```bash
python -m unittest discover tests/
```

---

## Screenshots

> _Add screenshots here after running the application._

---

## Author

**Tuhin** — [tuhinsbcl2-ctrl](https://github.com/tuhinsbcl2-ctrl)

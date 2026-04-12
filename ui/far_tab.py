"""
ui/far_tab.py — Fixed Asset Register (FAR) Import tab.

Workflow
--------
1.  Click **Import FAR** to load an Excel (.xlsx/.xls) or CSV file.
2.  The imported assets are shown in the *Imported Assets* table.
3.  Choose the Financial Year and DTA/DTL tax rate, then click **Calculate All**.
4.  Results are shown in the *Depreciation & DTA/DTL Results* table with
    columns for both Income Tax and Companies Act depreciation plus DTA/DTL.
5.  Click **Export to Excel** to save the results.

Calculation rules
-----------------
* **Income Tax (IT)**: WDV method using the *Dep Rate (%)* column from the FAR.
  If *Days Used* < 180, the 50 % half-year depreciation rule is applied.
* **Companies Act (CA)**: *Asset Type* is mapped to a Schedule II category to
  determine the useful life.  SLM or WDV is used per the *Dep Rate (%)* column.
  compute_depreciation_schedule() is used to extract the current-FY row.
* **DTA / DTL**: Difference between CA Closing WDV and IT Closing WDV × tax rate.

All pure calculation logic lives in utils/far_calculator.py so that it can
be unit-tested without requiring a display.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import DTA_DTL_TAX_RATES, generate_fy_options
from utils.formatters import format_currency, format_percentage
from utils.excel_handler import import_far_data, export_all_to_excel
from utils.far_calculator import calculate_asset
from ui.styles import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_SECONDARY,
    FONT_HEADING, FONT_LABEL, FONT_INPUT, FONT_BUTTON, FONT_TITLE,
    PAD_OUTER, PAD_INNER, PAD_BUTTON, ENTRY_WIDTH,
)

# ── Colour constants for result rows ──────────────────────────────────────────
_DTA_COLOUR = "#D5F5E3"   # light green
_DTL_COLOUR = "#FDEDEC"   # light red
_ALT_COLOUR = "#EBF5FB"   # light blue (alternating rows)


# ---------------------------------------------------------------------------
# Tab widget
# ---------------------------------------------------------------------------

class FarImportTab(ttk.Frame):
    """
    Tab widget for Fixed Asset Register (FAR) import and bulk depreciation
    calculation (Income Tax + Companies Act) with DTA/DTL summary.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.configure(style="TFrame")
        self._far_rows: list = []       # imported raw FAR rows
        self._result_rows: list = []    # calculated result dicts
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(padding=PAD_OUTER)

        # ── Title ────────────────────────────────────────────────────────────
        ttk.Label(
            self,
            text="Fixed Asset Register (FAR) — Bulk Import & Depreciation Calculator",
            font=FONT_TITLE, foreground=COLOR_PRIMARY,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, PAD_INNER))

        # ── Settings bar ────────────────────────────────────────────────────
        settings = ttk.LabelFrame(self, text="Settings", padding=PAD_INNER)
        settings.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, PAD_INNER))
        self._build_settings(settings)

        # ── Action buttons ───────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=PAD_INNER)
        self._build_buttons(btn_frame)

        # ── Status label ─────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="No file imported.")
        ttk.Label(
            self, textvariable=self._status_var,
            font=("Helvetica", 9), foreground="#555555",
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=PAD_INNER)

        # ── Imported assets table ────────────────────────────────────────────
        assets_frame = ttk.LabelFrame(self, text="Imported Assets", padding=PAD_INNER)
        assets_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=(PAD_INNER, 0))
        self._build_assets_table(assets_frame)

        # ── Results table ────────────────────────────────────────────────────
        results_frame = ttk.LabelFrame(
            self, text="Depreciation & DTA/DTL Results", padding=PAD_INNER,
        )
        results_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(PAD_INNER, 0))
        self._build_results_table(results_frame)

        # ── Summary bar ──────────────────────────────────────────────────────
        summary_frame = ttk.LabelFrame(self, text="Net Position", padding=PAD_INNER)
        summary_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(PAD_INNER, 0))
        self._build_summary(summary_frame)

        self.rowconfigure(4, weight=1)
        self.rowconfigure(5, weight=2)
        self.columnconfigure(0, weight=1)

    def _build_settings(self, parent):
        fy_options, current_fy = generate_fy_options()
        self._fy_var = tk.StringVar(value=current_fy)
        self._fy_options = fy_options

        ttk.Label(parent, text="Financial Year:", font=FONT_LABEL).grid(
            row=0, column=0, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        ttk.Combobox(
            parent, textvariable=self._fy_var, values=fy_options,
            width=ENTRY_WIDTH - 2, state="readonly", font=FONT_INPUT,
        ).grid(row=0, column=1, sticky="w", padx=(2, PAD_INNER * 3), pady=2)

        tax_rate_keys = list(DTA_DTL_TAX_RATES.keys())
        self._tax_rate_var = tk.StringVar(value=tax_rate_keys[0] if tax_rate_keys else "")
        ttk.Label(parent, text="Tax Rate (DTA/DTL):", font=FONT_LABEL).grid(
            row=0, column=2, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        ttk.Combobox(
            parent, textvariable=self._tax_rate_var, values=tax_rate_keys,
            width=ENTRY_WIDTH + 10, state="readonly", font=FONT_INPUT,
        ).grid(row=0, column=3, sticky="w", padx=(2, PAD_INNER), pady=2)

    def _build_buttons(self, parent):
        buttons = [
            ("Import FAR (Excel/CSV)", self._on_import,   "#555555"),
            ("Calculate All",          self._on_calculate, COLOR_PRIMARY),
            ("Clear",                  self._on_clear,     COLOR_WARNING),
            ("Export to Excel",        self._on_export,    COLOR_SUCCESS),
        ]
        for i, (text, cmd, colour) in enumerate(buttons):
            tk.Button(
                parent, text=text, command=cmd,
                bg=colour, fg="white", font=FONT_BUTTON,
                relief="flat", padx=PAD_BUTTON, pady=4,
                activebackground=colour, cursor="hand2",
            ).grid(row=0, column=i, padx=PAD_INNER, pady=PAD_INNER)

    def _build_assets_table(self, parent):
        columns = (
            "asset_id", "asset_name", "asset_type",
            "purchase_date", "cost", "opening_wdv",
            "additions", "deletions", "dep_rate", "days_used", "method",
        )
        headings = (
            "Asset ID", "Asset Name", "Asset Type",
            "Purchase / Use Date", "Cost (₹)", "Opening WDV (₹)",
            "Additions (₹)", "Deletions (₹)", "Dep Rate (%)", "Days Used", "Method",
        )
        widths = (70, 150, 120, 110, 100, 110, 90, 90, 80, 70, 60)

        self._assets_tree = ttk.Treeview(
            parent, columns=columns, show="headings", height=6,
        )
        for col, heading, w in zip(columns, headings, widths):
            self._assets_tree.heading(col, text=heading)
            anchor = "w" if col in ("asset_name", "asset_type") else "e"
            self._assets_tree.column(col, width=w, anchor=anchor, stretch=False)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._assets_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self._assets_tree.xview)
        self._assets_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._assets_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._assets_tree.tag_configure("odd",  background="#FFFFFF")
        self._assets_tree.tag_configure("even", background=_ALT_COLOUR)

    def _build_results_table(self, parent):
        columns = (
            "asset_name", "asset_type",
            "it_open", "it_dep", "it_close",
            "ca_open", "ca_dep", "ca_close",
            "diff", "rate", "dta", "dtl",
        )
        headings = (
            "Asset Name", "Asset Type",
            "IT Opening WDV (₹)", "IT Dep (₹)", "IT Closing WDV (₹)",
            "CA Opening WDV (₹)", "CA Dep (₹)", "CA Closing WDV (₹)",
            "Difference (₹)", "Rate %", "DTA (₹)", "DTL (₹)",
        )
        widths = (150, 120, 110, 100, 110, 110, 100, 110, 100, 70, 90, 90)

        self._results_tree = ttk.Treeview(
            parent, columns=columns, show="headings", height=8,
        )
        for col, heading, w in zip(columns, headings, widths):
            self._results_tree.heading(col, text=heading)
            anchor = "w" if col in ("asset_name", "asset_type") else "e"
            self._results_tree.column(col, width=w, anchor=anchor, stretch=False)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._results_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self._results_tree.xview)
        self._results_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._results_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._results_tree.tag_configure("odd",  background="#FFFFFF")
        self._results_tree.tag_configure("even", background=_ALT_COLOUR)
        self._results_tree.tag_configure("dta",  background=_DTA_COLOUR)
        self._results_tree.tag_configure("dtl",  background=_DTL_COLOUR)

    def _build_summary(self, parent):
        self._net_it_dep_var  = tk.StringVar(value="—")
        self._net_ca_dep_var  = tk.StringVar(value="—")
        self._net_dta_var     = tk.StringVar(value="—")
        self._net_dtl_var     = tk.StringVar(value="—")
        self._asset_count_var = tk.StringVar(value="—")

        pairs = [
            ("Assets Processed:",    self._asset_count_var, "#555555"),
            ("Total IT Dep (₹):",    self._net_it_dep_var,  COLOR_SECONDARY),
            ("Total CA Dep (₹):",    self._net_ca_dep_var,  COLOR_PRIMARY),
            ("Net DTA (₹):",         self._net_dta_var,     COLOR_SUCCESS),
            ("Net DTL (₹):",         self._net_dtl_var,     COLOR_WARNING),
        ]
        for col, (label_text, var, colour) in enumerate(pairs):
            ttk.Label(parent, text=label_text, font=FONT_HEADING, foreground=colour).grid(
                row=0, column=col * 2, padx=PAD_INNER, pady=2,
            )
            ttk.Label(parent, textvariable=var, font=FONT_HEADING).grid(
                row=0, column=col * 2 + 1, sticky="w", padx=(0, PAD_INNER),
            )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_import(self):
        filepath = filedialog.askopenfilename(
            title="Select FAR File (Excel or CSV)",
            filetypes=[
                ("Excel / CSV files", "*.xlsx *.xls *.csv"),
                ("Excel files",       "*.xlsx *.xls"),
                ("CSV files",         "*.csv"),
                ("All files",         "*.*"),
            ],
        )
        if not filepath:
            return

        rows, errors = import_far_data(filepath)
        if errors:
            messagebox.showwarning("Import Warnings", "\n".join(errors[:20]))
        if not rows:
            messagebox.showerror("Import Error", "No valid rows found in the file.")
            return

        self._far_rows = rows
        self._result_rows = []
        self._populate_assets_table(rows)
        self._clear_results_table()
        self._reset_summary()
        self._status_var.set(
            f"Imported {len(rows)} asset(s) from: {filepath}"
        )

    def _on_calculate(self):
        if not self._far_rows:
            messagebox.showwarning("Calculate", "Please import a FAR file first.")
            return

        fy_label = self._fy_var.get()
        tax_rate = DTA_DTL_TAX_RATES.get(self._tax_rate_var.get(), 25.168)

        results = []
        capital_gains = []
        for row in self._far_rows:
            try:
                result = calculate_asset(row, fy_label, tax_rate)
                results.append(result)
                if result.get("it_capital_gain"):
                    capital_gains.append(
                        f"  • {result['asset_name']}: "
                        f"₹{format_currency(result['it_capital_gain_amount'])}"
                    )
            except Exception as exc:
                messagebox.showwarning(
                    "Calculation Warning",
                    f"Error processing asset '{row.get('asset_name', '?')}': {exc}",
                )

        self._result_rows = results
        self._populate_results_table(results)
        self._update_summary(results)

        if capital_gains:
            messagebox.showinfo(
                "Capital Gain Detected",
                "The following assets have IT capital gains (deletions exceed block WDV):\n\n"
                + "\n".join(capital_gains)
                + "\n\nIT depreciation for these assets has been set to ₹0.",
            )

    def _on_clear(self):
        self._far_rows = []
        self._result_rows = []
        self._clear_assets_table()
        self._clear_results_table()
        self._reset_summary()
        self._status_var.set("No file imported.")

    def _on_export(self):
        if not self._result_rows:
            messagebox.showwarning("Export", "No results to export. Please calculate first.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save FAR Results",
        )
        if not filepath:
            return
        success, msg = export_all_to_excel(filepath, far_rows=self._result_rows)
        if success:
            messagebox.showinfo("Export", msg)
        else:
            messagebox.showerror("Export Error", msg)

    # ------------------------------------------------------------------
    # Table population helpers
    # ------------------------------------------------------------------

    def _populate_assets_table(self, rows):
        self._clear_assets_table()
        for i, row in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            raw_date = row.get("put_to_use_date") or row.get("purchase_date") or ""
            self._assets_tree.insert(
                "", "end",
                values=(
                    row.get("asset_id", ""),
                    row.get("asset_name", ""),
                    row.get("asset_type", ""),
                    raw_date,
                    format_currency(row.get("cost", 0.0)),
                    format_currency(row.get("opening_wdv", 0.0)),
                    format_currency(row.get("additions", 0.0)),
                    format_currency(row.get("deletions", 0.0)),
                    format_percentage(row.get("dep_rate", 0.0)),
                    str(int(row.get("days_used", 365))),
                    row.get("dep_method", "WDV"),
                ),
                tags=(tag,),
            )

    def _populate_results_table(self, results):
        self._clear_results_table()
        for i, r in enumerate(results):
            if r.get("dta", 0.0) > 0:
                tag = "dta"
            elif r.get("dtl", 0.0) > 0:
                tag = "dtl"
            else:
                tag = "even" if i % 2 == 0 else "odd"

            self._results_tree.insert(
                "", "end",
                values=(
                    r.get("asset_name", ""),
                    r.get("asset_type", ""),
                    format_currency(r.get("it_opening_wdv", 0.0)),
                    format_currency(r.get("it_depreciation", 0.0)),
                    format_currency(r.get("it_closing_wdv", 0.0)),
                    format_currency(r.get("ca_opening_wdv", 0.0)),
                    format_currency(r.get("ca_depreciation", 0.0)),
                    format_currency(r.get("ca_closing_wdv", 0.0)),
                    format_currency(r.get("difference", 0.0)),
                    format_percentage(r.get("tax_rate", 0.0)),
                    format_currency(r.get("dta", 0.0)),
                    format_currency(r.get("dtl", 0.0)),
                ),
                tags=(tag,),
            )

    def _update_summary(self, results):
        n = len(results)
        total_it  = sum(r.get("it_depreciation", 0.0) for r in results)
        total_ca  = sum(r.get("ca_depreciation", 0.0) for r in results)
        total_dta = sum(r.get("dta", 0.0) for r in results)
        total_dtl = sum(r.get("dtl", 0.0) for r in results)

        self._asset_count_var.set(str(n))
        self._net_it_dep_var.set(f"₹ {format_currency(total_it)}")
        self._net_ca_dep_var.set(f"₹ {format_currency(total_ca)}")
        self._net_dta_var.set(f"₹ {format_currency(total_dta)}")
        self._net_dtl_var.set(f"₹ {format_currency(total_dtl)}")

    def _reset_summary(self):
        for var in (
            self._net_it_dep_var, self._net_ca_dep_var,
            self._net_dta_var, self._net_dtl_var, self._asset_count_var,
        ):
            var.set("—")

    def _clear_assets_table(self):
        for item in self._assets_tree.get_children():
            self._assets_tree.delete(item)

    def _clear_results_table(self):
        for item in self._results_tree.get_children():
            self._results_tree.delete(item)

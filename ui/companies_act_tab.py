"""
ui/companies_act_tab.py — Tab for Companies Act depreciation input and output.

Layout
------
Top section : input form (asset details)
Bottom section : Treeview table showing the depreciation schedule
Buttons : Calculate, Clear, Import from Excel, Export to Excel
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

from config import (
    ASSET_CATEGORIES,
    COMPANIES_ACT_USEFUL_LIVES,
    DEPRECIATION_METHODS,
    DEFAULT_RESIDUAL_VALUE_PCT,
    generate_fy_options,
)
from models.companies_act import AssetInput, compute_depreciation_schedule
from utils.validators import (
    validate_positive_number,
    validate_positive_integer,
    validate_date,
    validate_percentage,
)
from utils.formatters import format_currency, parse_date
from utils.excel_handler import (
    import_companies_act_data,
    export_all_to_excel,
)
from ui.styles import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING,
    COLOR_BG, COLOR_FRAME_BG,
    FONT_HEADING, FONT_LABEL, FONT_INPUT, FONT_BUTTON, FONT_TITLE,
    PAD_OUTER, PAD_INNER, PAD_BUTTON,
    ENTRY_WIDTH, BUTTON_WIDTH,
    TREE_ROW_HEIGHT,
)


class CompaniesActTab(ttk.Frame):
    """
    Tab widget encapsulating the Companies Act depreciation form and results.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.configure(style="TFrame")
        self._schedule_rows = []   # last computed schedule
        self._tax_tab = None       # reference to IncomeTaxTab (wired by app.py)
        self._dta_tab = None       # reference to DtaTab (wired by app.py)
        self._build_ui()

    # ------------------------------------------------------------------
    # Cross-tab wiring
    # ------------------------------------------------------------------

    def set_tax_tab(self, tab):
        """Register the IncomeTaxTab so we can auto-fill it after Calculate."""
        self._tax_tab = tab

    def set_dta_tab(self, tab):
        """Register the DtaTab so we can auto-fill it after Calculate."""
        self._dta_tab = tab

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Assemble the entire tab layout."""
        self.configure(padding=PAD_OUTER)

        # ---- Title ----
        ttk.Label(
            self, text="Companies Act Depreciation (Schedule II)",
            font=FONT_TITLE, foreground=COLOR_PRIMARY,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, PAD_INNER))

        # ---- Input form ----
        form = ttk.LabelFrame(self, text="Asset Details", padding=PAD_INNER)
        form.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, PAD_INNER))
        self._build_form(form)

        # ---- Buttons ----
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=PAD_INNER)
        self._build_buttons(btn_frame)

        # ---- Results table ----
        result_frame = ttk.LabelFrame(self, text="Depreciation Schedule", padding=PAD_INNER)
        result_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=(PAD_INNER, 0))
        self._build_table(result_frame)

        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)

    def _build_form(self, parent):
        """Create labeled input fields."""
        # --- Financial Year selector (full-width row at the top) ---
        fy_options, current_fy = generate_fy_options()
        ttk.Label(parent, text="Financial Year (FY):", font=FONT_LABEL).grid(
            row=0, column=0, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        self._fy_var = tk.StringVar(value=current_fy)
        self._fy_options = fy_options
        ttk.Combobox(
            parent, textvariable=self._fy_var, values=fy_options,
            width=ENTRY_WIDTH - 2, state="readonly", font=FONT_INPUT,
        ).grid(row=0, column=1, sticky="w", padx=(2, PAD_INNER), pady=2)

        # --- Asset detail fields ---
        labels_entries = [
            ("Asset Name:",       "asset_name",        "entry",    None),
            ("Category:",         "category",          "combo",    ASSET_CATEGORIES),
            ("Cost of Asset (₹):","cost",              "entry",    None),
            ("Purchase Date:",    "purchase_date",     "entry",    None),
            ("Useful Life (yrs):","useful_life",       "entry",    None),
            ("Residual Value %:", "residual_value_pct","entry",    None),
            ("Method:",           "method",            "combo",    DEPRECIATION_METHODS),
        ]
        self._vars = {}
        for i, (label, key, wtype, options) in enumerate(labels_entries):
            row, col = divmod(i, 2)
            row += 1          # offset below the FY row
            col_base = col * 4  # 4 columns per pair: label + entry + (gap)
            ttk.Label(parent, text=label, font=FONT_LABEL).grid(
                row=row, column=col_base, sticky="e", padx=(PAD_INNER, 2), pady=2
            )
            var = tk.StringVar()
            self._vars[key] = var
            if wtype == "entry":
                widget = ttk.Entry(parent, textvariable=var, width=ENTRY_WIDTH, font=FONT_INPUT)
            else:
                widget = ttk.Combobox(
                    parent, textvariable=var, values=options,
                    width=ENTRY_WIDTH - 2, state="readonly", font=FONT_INPUT,
                )
                if options:
                    var.set(options[0])
            widget.grid(row=row, column=col_base + 1, sticky="w", padx=(2, PAD_INNER), pady=2)

        # Defaults
        self._vars["residual_value_pct"].set(str(DEFAULT_RESIDUAL_VALUE_PCT))
        self._vars["purchase_date"].set(date.today().strftime("%d/%m/%Y"))

        # Auto-populate useful life when category changes
        self._vars["category"].trace_add("write", self._on_category_change)
        self._on_category_change()

    def _build_buttons(self, parent):
        """Create action buttons."""
        buttons = [
            ("Calculate",         self._on_calculate, COLOR_PRIMARY),
            ("Clear",             self._on_clear,     COLOR_WARNING),
            ("Import from Excel", self._on_import,    "#555555"),
            ("Export to Excel",   self._on_export,    COLOR_SUCCESS),
        ]
        for i, (text, cmd, colour) in enumerate(buttons):
            btn = tk.Button(
                parent, text=text, command=cmd,
                bg=colour, fg="white", font=FONT_BUTTON,
                relief="flat", padx=PAD_BUTTON, pady=4,
                activebackground=colour, cursor="hand2",
            )
            btn.grid(row=0, column=i, padx=PAD_INNER, pady=PAD_INNER)

    def _build_table(self, parent):
        """Create Treeview with scrollbar for the depreciation schedule."""
        columns = ("year", "opening_wdv", "depreciation", "closing_wdv")
        headings = ("Year", "Opening WDV (₹)", "Depreciation (₹)", "Closing WDV (₹)")

        self._tree = ttk.Treeview(
            parent, columns=columns, show="headings",
            height=12,
        )
        for col, heading in zip(columns, headings):
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=180, anchor="e" if col != "year" else "w")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        # Alternating row colours
        self._tree.tag_configure("odd", background="#FFFFFF")
        self._tree.tag_configure("even", background="#EBF5FB")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_category_change(self, *_):
        """Auto-fill useful life when the category dropdown changes."""
        cat = self._vars["category"].get()
        life = COMPANIES_ACT_USEFUL_LIVES.get(cat, "")
        self._vars["useful_life"].set(str(life))

    def _on_calculate(self):
        """Validate inputs and compute the depreciation schedule."""
        errors = self._validate()
        if errors:
            messagebox.showerror("Input Error", "\n".join(errors))
            return

        asset = self._build_asset_input()
        self._schedule_rows = compute_depreciation_schedule(asset)
        self._populate_table(self._schedule_rows)

        # Auto-fill sister tabs with the results for the selected FY
        fy_label = self._fy_var.get()
        if self._tax_tab is not None:
            self._tax_tab.auto_fill_from_ca(asset, self._schedule_rows, fy_label)
        if self._dta_tab is not None:
            self._dta_tab.auto_fill_from_ca(asset, self._schedule_rows, fy_label)

    def _on_clear(self):
        """Reset all inputs and clear the table."""
        _, current_fy = generate_fy_options()
        self._fy_var.set(current_fy)
        for key, var in self._vars.items():
            if key == "category":
                var.set(ASSET_CATEGORIES[0])
            elif key == "method":
                var.set(DEPRECIATION_METHODS[0])
            elif key == "residual_value_pct":
                var.set(str(DEFAULT_RESIDUAL_VALUE_PCT))
            elif key == "purchase_date":
                var.set(date.today().strftime("%d/%m/%Y"))
            else:
                var.set("")
        self._on_category_change()
        self._clear_table()
        self._schedule_rows = []

    def _on_import(self):
        """Import asset data from an Excel file."""
        filepath = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not filepath:
            return
        rows, errors = import_companies_act_data(filepath)
        if errors:
            messagebox.showwarning("Import Warnings", "\n".join(errors))
        if rows:
            # Load the first valid row into the form
            r = rows[0]
            field_map = {
                "asset_name": "asset_name",
                "category": "category",
                "cost": "cost",
                "purchase_date": "purchase_date",
                "useful_life": "useful_life",
                "residual_value_pct": "residual_value_pct",
                "method": "method",
            }
            for field, var_key in field_map.items():
                if field in r and var_key in self._vars:
                    self._vars[var_key].set(str(r[field]))
            messagebox.showinfo("Import", f"Loaded {len(rows)} row(s). Showing first row.")

    def _on_export(self):
        """Export current depreciation schedule to Excel."""
        if not self._schedule_rows:
            messagebox.showwarning("Export", "No data to export. Please calculate first.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save Companies Act Report",
        )
        if not filepath:
            return
        asset_name = self._vars["asset_name"].get() or "Asset"
        success, msg = export_all_to_excel(
            filepath,
            ca_schedule_rows=self._schedule_rows,
            ca_asset_name=asset_name,
        )
        if success:
            messagebox.showinfo("Export", msg)
        else:
            messagebox.showerror("Export Error", msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate(self):
        """Return a list of error messages (empty list = all valid)."""
        errors = []
        v = self._vars

        if not v["asset_name"].get().strip():
            errors.append("Asset Name is required.")

        ok, msg = validate_positive_number(v["cost"].get(), "Cost of Asset")
        if not ok:
            errors.append(msg)
        else:
            cost = float(v["cost"].get())
            if cost == 0:
                errors.append("Cost of Asset must be greater than zero.")

        ok, msg = validate_date(v["purchase_date"].get(), "Purchase Date")
        if not ok:
            errors.append(msg)

        ok, msg = validate_positive_integer(v["useful_life"].get(), "Useful Life")
        if not ok:
            errors.append(msg)

        ok, msg = validate_percentage(v["residual_value_pct"].get(), "Residual Value %")
        if not ok:
            errors.append(msg)

        return errors

    def _build_asset_input(self) -> AssetInput:
        """Construct an AssetInput from the current form values."""
        v = self._vars
        return AssetInput(
            asset_name=v["asset_name"].get().strip(),
            category=v["category"].get(),
            cost=float(v["cost"].get()),
            purchase_date=parse_date(v["purchase_date"].get()),
            useful_life=int(v["useful_life"].get()),
            residual_value_pct=float(v["residual_value_pct"].get()),
            method=v["method"].get(),
        )

    def _clear_table(self):
        """Remove all rows from the Treeview."""
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _populate_table(self, rows):
        """Fill the Treeview with depreciation schedule rows."""
        self._clear_table()
        for i, row in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                values=(
                    row.year_label,
                    format_currency(row.opening_wdv),
                    format_currency(row.depreciation),
                    format_currency(row.closing_wdv),
                ),
                tags=(tag,),
            )

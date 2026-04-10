"""
ui/income_tax_tab.py — Tab for Income Tax depreciation input and output.

Layout
------
Top section : input form (block details)
Middle : results Treeview table
Bottom buttons : Calculate, Clear, Import, Export
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import INCOME_TAX_BLOCKS, CA_TO_IT_BLOCK_MAP, generate_fy_options
from models.income_tax import TaxBlockInput, compute_tax_depreciation
from utils.validators import validate_positive_number, validate_percentage
from utils.formatters import format_currency, format_percentage
from utils.excel_handler import import_income_tax_data, export_all_to_excel
from ui.styles import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING,
    FONT_LABEL, FONT_INPUT, FONT_BUTTON, FONT_TITLE,
    PAD_OUTER, PAD_INNER, PAD_BUTTON, ENTRY_WIDTH,
)


class IncomeTaxTab(ttk.Frame):
    """
    Tab widget for Income Tax (block-wise WDV) depreciation.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._results = []     # list of TaxDepreciationResult
        self._dta_tab = None   # reference to DtaTab (wired by app.py)
        self._build_ui()

    # ------------------------------------------------------------------
    # Cross-tab wiring
    # ------------------------------------------------------------------

    def set_dta_tab(self, tab):
        """Register the DtaTab so we can auto-fill it after Calculate."""
        self._dta_tab = tab

    def auto_fill_from_ca(self, asset, schedule, fy_label: str):
        """
        Auto-fill this tab from a Companies Act calculation result.

        Parameters
        ----------
        asset    : AssetInput — the CA asset whose schedule was computed
        schedule : list of DepreciationRow — the full CA depreciation schedule
        fy_label : str — e.g. "FY 2024-25"
        """
        # Sync FY selector
        if fy_label in self._fy_options:
            self._fy_var.set(fy_label)

        # Map CA category to the nearest IT block
        it_block = CA_TO_IT_BLOCK_MAP.get(asset.category, list(INCOME_TAX_BLOCKS.keys())[0])
        self._vars["block_name"].set(it_block)

        # Find the CA row for the selected FY and use its opening WDV
        ca_row = next((r for r in schedule if r.year_label == fy_label), None)
        if ca_row is not None:
            self._vars["opening_wdv"].set(str(round(ca_row.opening_wdv, 2)))
        else:
            self._vars["opening_wdv"].set("0")

        # Sync the IT rate to the mapped block
        self._on_block_change()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(padding=PAD_OUTER)

        ttk.Label(
            self, text="Income Tax Depreciation (Block-wise WDV)",
            font=FONT_TITLE, foreground=COLOR_PRIMARY,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, PAD_INNER))

        form = ttk.LabelFrame(self, text="Block Details", padding=PAD_INNER)
        form.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, PAD_INNER))
        self._build_form(form)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=PAD_INNER)
        self._build_buttons(btn_frame)

        result_frame = ttk.LabelFrame(self, text="Tax Depreciation Results", padding=PAD_INNER)
        result_frame.grid(row=3, column=0, columnspan=4, sticky="nsew")
        self._build_table(result_frame)

        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)

    def _build_form(self, parent):
        block_names = list(INCOME_TAX_BLOCKS.keys())

        # --- Financial Year selector ---
        fy_options, current_fy = generate_fy_options()
        self._fy_var = tk.StringVar(value=current_fy)
        self._fy_options = fy_options
        ttk.Label(parent, text="Financial Year (FY):", font=FONT_LABEL).grid(
            row=0, column=0, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        ttk.Combobox(
            parent, textvariable=self._fy_var, values=fy_options,
            width=ENTRY_WIDTH - 2, state="readonly", font=FONT_INPUT,
        ).grid(row=0, column=1, sticky="w", padx=(2, PAD_INNER), pady=2)

        # --- Block detail fields ---
        fields = [
            ("Block Name:",          "block_name",        "combo",    block_names),
            ("Opening WDV (₹):",     "opening_wdv",       "entry",    None),
            ("Additions (₹):",       "additions",         "entry",    None),
            ("Deletions/Sales (₹):", "deletions",         "entry",    None),
            ("Depreciation Rate %:", "rate",              "entry",    None),
        ]

        self._vars = {}
        self._less_180_var = tk.BooleanVar(value=False)

        for i, (label, key, wtype, options) in enumerate(fields):
            row, col = divmod(i, 2)
            row += 1          # offset below the FY row
            col_base = col * 4
            ttk.Label(parent, text=label, font=FONT_LABEL).grid(
                row=row, column=col_base, sticky="e", padx=(PAD_INNER, 2), pady=2,
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

        # 180-day checkbox
        cb_row = (len(fields) + 1) // 2 + 2
        ttk.Checkbutton(
            parent,
            text="Asset used for less than 180 days (50% depreciation applies)",
            variable=self._less_180_var,
        ).grid(row=cb_row, column=0, columnspan=6, sticky="w", padx=PAD_INNER, pady=4)

        # Defaults for numeric fields
        for key in ("opening_wdv", "additions", "deletions"):
            self._vars[key].set("0")

        # Auto-fill rate when block changes
        self._vars["block_name"].trace_add("write", self._on_block_change)
        self._on_block_change()

    def _build_buttons(self, parent):
        buttons = [
            ("Calculate",         self._on_calculate, COLOR_PRIMARY),
            ("Clear",             self._on_clear,     COLOR_WARNING),
            ("Import from Excel", self._on_import,    "#555555"),
            ("Export to Excel",   self._on_export,    COLOR_SUCCESS),
        ]
        for i, (text, cmd, colour) in enumerate(buttons):
            tk.Button(
                parent, text=text, command=cmd,
                bg=colour, fg="white", font=FONT_BUTTON,
                relief="flat", padx=PAD_BUTTON, pady=4,
                activebackground=colour, cursor="hand2",
            ).grid(row=0, column=i, padx=PAD_INNER, pady=PAD_INNER)

    def _build_table(self, parent):
        columns = (
            "block", "opening_wdv", "additions", "deletions",
            "adjusted_wdv", "rate", "depreciation", "closing_wdv",
        )
        headings = (
            "Block", "Opening WDV", "Additions", "Deletions",
            "Adjusted WDV", "Rate %", "Depreciation", "Closing WDV",
        )
        self._tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for col, heading in zip(columns, headings):
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=130, anchor="e" if col != "block" else "w")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._tree.tag_configure("odd", background="#FFFFFF")
        self._tree.tag_configure("even", background="#EBF5FB")
        self._tree.tag_configure("capital_gain", background="#FDEBD0")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_block_change(self, *_):
        block = self._vars["block_name"].get()
        rate = INCOME_TAX_BLOCKS.get(block, "")
        self._vars["rate"].set(str(rate))

    def _on_calculate(self):
        errors = self._validate()
        if errors:
            messagebox.showerror("Input Error", "\n".join(errors))
            return

        block_input = TaxBlockInput(
            block_name=self._vars["block_name"].get(),
            opening_wdv=float(self._vars["opening_wdv"].get()),
            additions=float(self._vars["additions"].get()),
            deletions=float(self._vars["deletions"].get()),
            rate=float(self._vars["rate"].get()),
            less_than_180_days=self._less_180_var.get(),
        )
        result = compute_tax_depreciation(block_input)
        self._results = [result]
        self._populate_table(self._results)

        if result.capital_gain_flag:
            messagebox.showwarning(
                "Capital Gain",
                f"Deletions exceed the block value.\n"
                f"Notional capital gain: ₹{format_currency(result.capital_gain_amount)}\n"
                f"Depreciation has been set to ₹0.",
            )

        # Auto-fill DTA tab with the IT closing WDV
        if self._dta_tab is not None:
            self._dta_tab.auto_fill_from_it(result, self._fy_var.get())

    def _on_clear(self):
        blocks = list(INCOME_TAX_BLOCKS.keys())
        self._vars["block_name"].set(blocks[0] if blocks else "")
        for key in ("opening_wdv", "additions", "deletions"):
            self._vars[key].set("0")
        self._less_180_var.set(False)
        self._on_block_change()
        self._clear_table()
        self._results = []
        _, current_fy = generate_fy_options()
        self._fy_var.set(current_fy)

    def _on_import(self):
        filepath = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not filepath:
            return
        rows, errors = import_income_tax_data(filepath)
        if errors:
            messagebox.showwarning("Import Warnings", "\n".join(errors))
        if rows:
            r = rows[0]
            field_map = {
                "block_name": "block_name",
                "opening_wdv": "opening_wdv",
                "additions": "additions",
                "deletions": "deletions",
                "rate": "rate",
            }
            for field, var_key in field_map.items():
                if field in r and var_key in self._vars:
                    self._vars[var_key].set(str(r[field]))
            messagebox.showinfo("Import", f"Loaded {len(rows)} row(s). Showing first row.")

    def _on_export(self):
        if not self._results:
            messagebox.showwarning("Export", "No data to export. Please calculate first.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save Tax Depreciation Report",
        )
        if not filepath:
            return
        success, msg = export_all_to_excel(filepath, tax_results=self._results)
        if success:
            messagebox.showinfo("Export", msg)
        else:
            messagebox.showerror("Export Error", msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate(self):
        errors = []
        v = self._vars
        for key, label in [
            ("opening_wdv", "Opening WDV"),
            ("additions", "Additions"),
            ("deletions", "Deletions"),
        ]:
            ok, msg = validate_positive_number(v[key].get(), label)
            if not ok:
                errors.append(msg)
        ok, msg = validate_percentage(v["rate"].get(), "Depreciation Rate")
        if not ok:
            errors.append(msg)
        return errors

    def _clear_table(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _populate_table(self, results):
        self._clear_table()
        for i, res in enumerate(results):
            tag = "capital_gain" if res.capital_gain_flag else ("even" if i % 2 == 0 else "odd")
            self._tree.insert(
                "", "end",
                values=(
                    res.block_name,
                    format_currency(res.opening_wdv),
                    format_currency(res.additions),
                    format_currency(res.deletions),
                    format_currency(res.adjusted_wdv),
                    format_percentage(res.effective_rate),
                    format_currency(res.depreciation),
                    format_currency(res.closing_wdv),
                ),
                tags=(tag,),
            )

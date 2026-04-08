"""
ui/dta_tab.py — Tab for Deferred Tax Asset / Deferred Tax Liability calculation.

Layout
------
Top section : input form (asset name, book value, tax value, tax rate)
Middle : Treeview table showing per-asset DTA/DTL
Bottom : Summary row (Net DTA or Net DTL) + buttons
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import DTA_DTL_TAX_RATES
from models.dta_dtl import DtaAssetInput, compute_dta_dtl
from utils.validators import validate_positive_number, validate_percentage
from utils.formatters import format_currency, format_percentage
from utils.excel_handler import export_all_to_excel
from ui.styles import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_SECONDARY,
    FONT_LABEL, FONT_INPUT, FONT_BUTTON, FONT_TITLE, FONT_HEADING,
    PAD_OUTER, PAD_INNER, PAD_BUTTON, ENTRY_WIDTH,
)


class DtaTab(ttk.Frame):
    """
    Tab widget for DTA / DTL calculation across multiple assets.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self._asset_inputs = []   # accumulated list of DtaAssetInput
        self._summary = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(padding=PAD_OUTER)

        ttk.Label(
            self, text="Deferred Tax Asset / Liability (DTA / DTL) Calculator",
            font=FONT_TITLE, foreground=COLOR_SECONDARY,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, PAD_INNER))

        form = ttk.LabelFrame(self, text="Add Asset Entry", padding=PAD_INNER)
        form.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, PAD_INNER))
        self._build_form(form)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=PAD_INNER)
        self._build_buttons(btn_frame)

        result_frame = ttk.LabelFrame(self, text="DTA / DTL Breakdown", padding=PAD_INNER)
        result_frame.grid(row=3, column=0, columnspan=4, sticky="nsew")
        self._build_table(result_frame)

        # Summary section
        summary_frame = ttk.LabelFrame(self, text="Net Position", padding=PAD_INNER)
        summary_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(PAD_INNER, 0))
        self._build_summary(summary_frame)

        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)

    def _build_form(self, parent):
        fields = [
            ("Asset Name:",            "asset_name",  "entry", None),
            ("Book Value (CA WDV ₹):", "book_value",  "entry", None),
            ("Tax Value (IT WDV ₹):",  "tax_value",   "entry", None),
            ("Tax Rate:",              "tax_rate",    "combo", list(DTA_DTL_TAX_RATES.keys())),
        ]
        self._vars = {}
        for i, (label, key, wtype, options) in enumerate(fields):
            row, col = divmod(i, 2)
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
                    width=ENTRY_WIDTH + 10, state="readonly", font=FONT_INPUT,
                )
                if options:
                    var.set(options[0])
            widget.grid(row=row, column=col_base + 1, sticky="w", padx=(2, PAD_INNER), pady=2)

        # Custom tax rate entry (shown next to combo)
        ttk.Label(parent, text="Custom Rate %:", font=FONT_LABEL).grid(
            row=1, column=4, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        self._custom_rate_var = tk.StringVar()
        ttk.Entry(
            parent, textvariable=self._custom_rate_var, width=10, font=FONT_INPUT,
        ).grid(row=1, column=5, sticky="w", padx=(2, PAD_INNER), pady=2)

    def _build_buttons(self, parent):
        buttons = [
            ("Add Asset",         self._on_add_asset,    COLOR_PRIMARY),
            ("Calculate Net",     self._on_calculate,    COLOR_SECONDARY),
            ("Clear All",         self._on_clear,        COLOR_WARNING),
            ("Export to Excel",   self._on_export,       COLOR_SUCCESS),
        ]
        for i, (text, cmd, colour) in enumerate(buttons):
            tk.Button(
                parent, text=text, command=cmd,
                bg=colour, fg="white", font=FONT_BUTTON,
                relief="flat", padx=PAD_BUTTON, pady=4,
                activebackground=colour, cursor="hand2",
            ).grid(row=0, column=i, padx=PAD_INNER, pady=PAD_INNER)

    def _build_table(self, parent):
        columns = ("asset", "book_value", "tax_value", "difference", "tax_rate", "dta", "dtl")
        headings = ("Asset", "Book Value (₹)", "Tax Value (₹)", "Difference (₹)", "Rate %", "DTA (₹)", "DTL (₹)")
        self._tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for col, heading in zip(columns, headings):
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=150, anchor="e" if col != "asset" else "w")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._tree.tag_configure("odd", background="#FFFFFF")
        self._tree.tag_configure("even", background="#EBF5FB")
        self._tree.tag_configure("dta_row", background="#D5F5E3")   # green tint for DTA
        self._tree.tag_configure("dtl_row", background="#FDEDEC")   # red tint for DTL

    def _build_summary(self, parent):
        self._net_dta_var = tk.StringVar(value="—")
        self._net_dtl_var = tk.StringVar(value="—")

        ttk.Label(parent, text="Net DTA:", font=FONT_HEADING, foreground=COLOR_SUCCESS).grid(
            row=0, column=0, padx=PAD_INNER, pady=2,
        )
        ttk.Label(parent, textvariable=self._net_dta_var, font=FONT_HEADING).grid(
            row=0, column=1, sticky="w", padx=PAD_INNER,
        )

        ttk.Label(parent, text="Net DTL:", font=FONT_HEADING, foreground=COLOR_WARNING).grid(
            row=0, column=2, padx=PAD_INNER, pady=2,
        )
        ttk.Label(parent, textvariable=self._net_dtl_var, font=FONT_HEADING).grid(
            row=0, column=3, sticky="w", padx=PAD_INNER,
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_add_asset(self):
        """Validate the current form and add the asset to the pending list."""
        errors = self._validate_asset_form()
        if errors:
            messagebox.showerror("Input Error", "\n".join(errors))
            return

        tax_rate = self._resolve_tax_rate()
        if tax_rate is None:
            return

        self._asset_inputs.append(DtaAssetInput(
            asset_name=self._vars["asset_name"].get().strip(),
            book_value=float(self._vars["book_value"].get()),
            tax_value=float(self._vars["tax_value"].get()),
            tax_rate=tax_rate,
        ))

        # Clear form for next entry
        self._vars["asset_name"].set("")
        self._vars["book_value"].set("")
        self._vars["tax_value"].set("")
        self._custom_rate_var.set("")

        messagebox.showinfo(
            "Asset Added",
            f"Asset added. Total: {len(self._asset_inputs)}. "
            "Click 'Calculate Net' to see the DTA/DTL breakdown.",
        )

    def _on_calculate(self):
        """Compute DTA/DTL for all added assets and display results."""
        if not self._asset_inputs:
            messagebox.showwarning("No Data", "Please add at least one asset.")
            return

        self._summary = compute_dta_dtl(self._asset_inputs)
        self._populate_table(self._summary.rows)
        self._net_dta_var.set(f"₹ {format_currency(self._summary.net_dta)}")
        self._net_dtl_var.set(f"₹ {format_currency(self._summary.net_dtl)}")

    def _on_clear(self):
        self._asset_inputs = []
        self._summary = None
        self._clear_table()
        self._net_dta_var.set("—")
        self._net_dtl_var.set("—")
        for var in self._vars.values():
            var.set("")
        self._custom_rate_var.set("")
        # Reset combo to first option
        tax_rate_keys = list(DTA_DTL_TAX_RATES.keys())
        if tax_rate_keys:
            self._vars["tax_rate"].set(tax_rate_keys[0])

    def _on_export(self):
        if not self._summary:
            messagebox.showwarning("Export", "No data to export. Please calculate first.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save DTA/DTL Report",
        )
        if not filepath:
            return
        success, msg = export_all_to_excel(filepath, dta_summary=self._summary)
        if success:
            messagebox.showinfo("Export", msg)
        else:
            messagebox.showerror("Export Error", msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_asset_form(self):
        errors = []
        v = self._vars
        if not v["asset_name"].get().strip():
            errors.append("Asset Name is required.")
        ok, msg = validate_positive_number(v["book_value"].get(), "Book Value")
        if not ok:
            errors.append(msg)
        ok, msg = validate_positive_number(v["tax_value"].get(), "Tax Value")
        if not ok:
            errors.append(msg)
        return errors

    def _resolve_tax_rate(self):
        """
        Return the effective tax rate (float).

        Priority: custom rate > dropdown selection.
        """
        custom = self._custom_rate_var.get().strip()
        if custom:
            ok, msg = validate_percentage(custom, "Custom Tax Rate")
            if not ok:
                messagebox.showerror("Input Error", msg)
                return None
            return float(custom)
        selected = self._vars["tax_rate"].get()
        return DTA_DTL_TAX_RATES.get(selected, 25.168)

    def _clear_table(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _populate_table(self, rows):
        self._clear_table()
        for i, row in enumerate(rows):
            if row.dta > 0:
                tag = "dta_row"
            elif row.dtl > 0:
                tag = "dtl_row"
            else:
                tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                values=(
                    row.asset_name,
                    format_currency(row.book_value),
                    format_currency(row.tax_value),
                    format_currency(row.difference),
                    format_percentage(row.tax_rate),
                    format_currency(row.dta),
                    format_currency(row.dtl),
                ),
                tags=(tag,),
            )

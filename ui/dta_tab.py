"""
ui/dta_tab.py — Tab for Deferred Tax Asset / Deferred Tax Liability calculation.

Layout
------
Top section : input form (FY selector, auto-filled asset/book/tax values,
              tax-rate dropdown, and the single editable opening-balance field)
Middle : Treeview table showing DTA/DTL breakdown with movement
Bottom : Summary row (opening, current year, closing, P&L movement) + buttons
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import DTA_DTL_TAX_RATES, generate_fy_options
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
    Tab widget for DTA / DTL calculation.

    Fields are auto-filled from the Companies Act and Tax Depreciation tabs.
    The only editable input field is *Opening DTA/DTL Balance*.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
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

        form = ttk.LabelFrame(self, text="Asset Entry", padding=PAD_INNER)
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
        """
        Build the input form.

        * FY selector      — editable (combo)
        * Asset Name       — read-only (auto-filled from CA tab)
        * Book Value       — read-only (auto-filled from CA closing WDV)
        * Tax Value        — read-only (auto-filled from IT closing WDV)
        * Tax Rate         — editable dropdown
        * Opening Balance  — THE only free-text editable field
        """
        fy_options, current_fy = generate_fy_options()
        self._fy_options = fy_options
        self._fy_var = tk.StringVar(value=current_fy)

        # Row 0 — FY selector
        ttk.Label(parent, text="Financial Year (FY):", font=FONT_LABEL).grid(
            row=0, column=0, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        ttk.Combobox(
            parent, textvariable=self._fy_var, values=fy_options,
            width=ENTRY_WIDTH - 2, state="readonly", font=FONT_INPUT,
        ).grid(row=0, column=1, sticky="w", padx=(2, PAD_INNER), pady=2)

        # Remaining fields: asset_name, book_value, tax_value are read-only;
        # tax_rate is a dropdown; opening_balance is the sole editable entry.
        field_defs = [
            # (label,                  key,               wtype,   options,               editable)
            ("Asset Name:",            "asset_name",      "entry", None,                  False),
            ("Book Value (CA WDV ₹):","book_value",      "entry", None,                  False),
            ("Tax Value (IT WDV ₹):", "tax_value",       "entry", None,                  False),
            ("Tax Rate:",              "tax_rate",        "combo", list(DTA_DTL_TAX_RATES.keys()), True),
            ("Opening DTA/DTL (₹):\n(+ = DTA, − = DTL)",
                                       "opening_balance", "entry", None,                  True),
        ]

        self._vars = {}
        self._entry_widgets = {}

        for i, (label, key, wtype, options, editable) in enumerate(field_defs):
            row, col = divmod(i, 2)
            row += 1      # offset below the FY row
            col_base = col * 4

            ttk.Label(parent, text=label, font=FONT_LABEL).grid(
                row=row, column=col_base, sticky="e", padx=(PAD_INNER, 2), pady=2,
            )
            var = tk.StringVar()
            self._vars[key] = var

            if wtype == "entry":
                state = "normal" if editable else "readonly"
                widget = ttk.Entry(
                    parent, textvariable=var, width=ENTRY_WIDTH, font=FONT_INPUT,
                    state=state,
                )
            else:  # combo
                widget = ttk.Combobox(
                    parent, textvariable=var, values=options,
                    width=ENTRY_WIDTH + 10, state="readonly", font=FONT_INPUT,
                )
                if options:
                    var.set(options[0])

            widget.grid(row=row, column=col_base + 1, sticky="w", padx=(2, PAD_INNER), pady=2)
            self._entry_widgets[key] = widget

        # Default opening balance to 0
        self._vars["opening_balance"].set("0")

        # Hint label for opening balance
        ttk.Label(
            parent,
            text="Tip: Opening balance is carried from the previous year's DTA/DTL.",
            font=("Helvetica", 8), foreground="#7F8C8D",
        ).grid(
            row=(len(field_defs) + 1) // 2 + 1, column=0, columnspan=6,
            sticky="w", padx=PAD_INNER, pady=(0, 2),
        )

    def _build_buttons(self, parent):
        buttons = [
            ("Calculate",       self._on_calculate, COLOR_PRIMARY),
            ("Clear",           self._on_clear,     COLOR_WARNING),
            ("Export to Excel", self._on_export,    COLOR_SUCCESS),
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
            "asset", "book_value", "tax_value", "difference",
            "tax_rate", "dta", "dtl", "opening_bal", "movement", "closing_bal",
        )
        headings = (
            "Asset", "Book Value (₹)", "Tax Value (₹)", "Difference (₹)",
            "Rate %", "DTA (₹)", "DTL (₹)",
            "Opening Bal (₹)", "P&L Movement (₹)", "Closing Bal (₹)",
        )
        self._tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
        for col, heading in zip(columns, headings):
            self._tree.heading(col, text=heading)
            width = 100 if col != "asset" else 130
            self._tree.column(col, width=width, anchor="e" if col != "asset" else "w")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._tree.tag_configure("odd",     background="#FFFFFF")
        self._tree.tag_configure("even",    background="#EBF5FB")
        self._tree.tag_configure("dta_row", background="#D5F5E3")
        self._tree.tag_configure("dtl_row", background="#FDEDEC")

    def _build_summary(self, parent):
        self._opening_bal_var  = tk.StringVar(value="—")
        self._current_dta_var  = tk.StringVar(value="—")
        self._current_dtl_var  = tk.StringVar(value="—")
        self._movement_var     = tk.StringVar(value="—")
        self._closing_bal_var  = tk.StringVar(value="—")

        pairs = [
            ("Opening Balance:", self._opening_bal_var,  "#555555"),
            ("Current Year DTA:", self._current_dta_var, COLOR_SUCCESS),
            ("Current Year DTL:", self._current_dtl_var, COLOR_WARNING),
            ("P&L Movement:",     self._movement_var,    COLOR_SECONDARY),
            ("Closing Balance:",  self._closing_bal_var, COLOR_PRIMARY),
        ]
        for col, (label_text, var, colour) in enumerate(pairs):
            ttk.Label(parent, text=label_text, font=FONT_HEADING, foreground=colour).grid(
                row=0, column=col * 2, padx=PAD_INNER, pady=2,
            )
            ttk.Label(parent, textvariable=var, font=FONT_HEADING).grid(
                row=0, column=col * 2 + 1, sticky="w", padx=(0, PAD_INNER),
            )

    # ------------------------------------------------------------------
    # Cross-tab auto-fill methods
    # ------------------------------------------------------------------

    def auto_fill_from_ca(self, asset, schedule, fy_label: str):
        """
        Auto-fill asset name and book value (CA closing WDV for *fy_label*).

        Called by CompaniesActTab after each successful Calculate.
        """
        # Sync FY
        if fy_label in self._fy_options:
            self._fy_var.set(fy_label)

        # Asset name
        self._set_readonly_entry("asset_name", asset.asset_name)

        # Book value = CA closing WDV for the selected FY
        ca_row = next((r for r in schedule if r.year_label == fy_label), None)
        book_val = round(ca_row.closing_wdv, 2) if ca_row is not None else 0.0
        self._set_readonly_entry("book_value", str(book_val))

    def auto_fill_from_it(self, result, fy_label: str):
        """
        Auto-fill tax value (IT closing WDV) from an IncomeTaxTab result.

        Called by IncomeTaxTab after each successful Calculate.
        """
        # Sync FY
        if fy_label in self._fy_options:
            self._fy_var.set(fy_label)

        # Tax value = IT closing WDV
        self._set_readonly_entry("tax_value", str(round(result.closing_wdv, 2)))

    def _set_readonly_entry(self, key: str, value: str):
        """Temporarily unlock a read-only entry, set its value, then re-lock."""
        widget = self._entry_widgets.get(key)
        if widget is not None:
            widget.configure(state="normal")
            self._vars[key].set(value)
            widget.configure(state="readonly")
        else:
            self._vars[key].set(value)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_calculate(self):
        """Compute DTA/DTL using the auto-filled values and the opening balance."""
        errors = self._validate()
        if errors:
            messagebox.showerror("Input Error", "\n".join(errors))
            return

        tax_rate = self._resolve_tax_rate()
        if tax_rate is None:
            return

        # Parse opening balance (signed float)
        ob_str = self._vars["opening_balance"].get().strip() or "0"
        try:
            opening_balance = float(ob_str)
        except ValueError:
            messagebox.showerror("Input Error", "Opening Balance must be a number.")
            return

        asset_input = DtaAssetInput(
            asset_name=self._vars["asset_name"].get().strip() or "Asset",
            book_value=float(self._vars["book_value"].get() or "0"),
            tax_value=float(self._vars["tax_value"].get() or "0"),
            tax_rate=tax_rate,
            opening_balance=opening_balance,
        )

        self._summary = compute_dta_dtl([asset_input])
        self._populate_table(self._summary.rows)

        # Update summary panel
        s = self._summary
        sign_opening = "DTA" if s.total_opening_balance >= 0 else "DTL"
        sign_closing = "DTA" if s.net_closing_balance >= 0 else "DTL"
        self._opening_bal_var.set(
            f"₹ {format_currency(abs(s.total_opening_balance))} ({sign_opening})"
        )
        self._current_dta_var.set(f"₹ {format_currency(s.net_dta)}")
        self._current_dtl_var.set(f"₹ {format_currency(s.net_dtl)}")
        self._movement_var.set(f"₹ {format_currency(s.net_movement)}")
        self._closing_bal_var.set(
            f"₹ {format_currency(abs(s.net_closing_balance))} ({sign_closing})"
        )

    def _on_clear(self):
        """Clear all fields and results."""
        self._summary = None
        self._clear_table()

        # Reset summary labels
        for var in (
            self._opening_bal_var, self._current_dta_var,
            self._current_dtl_var, self._movement_var, self._closing_bal_var,
        ):
            var.set("—")

        # Reset form fields
        for key in ("asset_name", "book_value", "tax_value"):
            self._set_readonly_entry(key, "")

        self._vars["opening_balance"].set("0")

        tax_rate_keys = list(DTA_DTL_TAX_RATES.keys())
        if tax_rate_keys:
            self._vars["tax_rate"].set(tax_rate_keys[0])

        _, current_fy = generate_fy_options()
        self._fy_var.set(current_fy)

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

    def _validate(self):
        errors = []
        v = self._vars
        # book_value and tax_value may be empty if not yet auto-filled
        for key, label in [("book_value", "Book Value"), ("tax_value", "Tax Value")]:
            val = v[key].get().strip()
            if not val:
                errors.append(f"{label} is not yet filled. Please calculate from the Companies Act / Tax Depreciation tab first.")
            else:
                ok, msg = validate_positive_number(val, label)
                if not ok:
                    errors.append(msg)
        return errors

    def _resolve_tax_rate(self):
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
                    format_currency(row.opening_balance),
                    format_currency(row.movement),
                    format_currency(row.closing_balance),
                ),
                tags=(tag,),
            )

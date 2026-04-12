"""
ui/history_tab.py — FAR History tab backed by the local SQLite database.

Features
--------
* Browse saved FAR results by Financial Year.
* Rollover the closing WDV / DTA / DTL of one year into the next as opening
  balances, ready for import or calculation.
* Delete historical records for a specific FY.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from config import generate_fy_options
from utils.database import db
from utils.formatters import format_currency
from utils.logger import get_logger
from ui.styles import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_SECONDARY,
    FONT_HEADING, FONT_LABEL, FONT_INPUT, FONT_BUTTON, FONT_TITLE,
    PAD_OUTER, PAD_INNER, PAD_BUTTON, ENTRY_WIDTH,
)

log = get_logger(__name__)

_ALT_COLOUR = "#EBF5FB"


class HistoryTab(ttk.Frame):
    """Tab for browsing and managing the local FAR history database."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.configure(style="TFrame")
        self._far_tab = None    # injected by app.py after construction
        self._build_ui()

    def set_far_tab(self, far_tab) -> None:
        """Inject a reference to FarImportTab for rollover → pre-load."""
        self._far_tab = far_tab

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(padding=PAD_OUTER)

        ttk.Label(
            self,
            text="FAR History — Asset Depreciation Across Financial Years",
            font=FONT_TITLE, foreground=COLOR_PRIMARY,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, PAD_INNER))

        # ── Filter bar ────────────────────────────────────────────────────────
        filter_frame = ttk.LabelFrame(self, text="Filter", padding=PAD_INNER)
        filter_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, PAD_INNER))
        self._build_filter(filter_frame)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=PAD_INNER)
        self._build_buttons(btn_frame)

        # ── History table ─────────────────────────────────────────────────────
        tbl_frame = ttk.LabelFrame(self, text="Records", padding=PAD_INNER)
        tbl_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=(PAD_INNER, 0))
        self._build_table(tbl_frame)

        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)

    def _build_filter(self, parent):
        fy_options, current_fy = generate_fy_options()
        self._fy_var = tk.StringVar(value=current_fy)

        ttk.Label(parent, text="Financial Year:", font=FONT_LABEL).grid(
            row=0, column=0, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        self._fy_combo = ttk.Combobox(
            parent, textvariable=self._fy_var, values=fy_options,
            width=ENTRY_WIDTH, state="readonly", font=FONT_INPUT,
        )
        self._fy_combo.grid(row=0, column=1, sticky="w", padx=(2, PAD_INNER * 2), pady=2)

        ttk.Label(parent, text="Rollover to:", font=FONT_LABEL).grid(
            row=0, column=2, sticky="e", padx=(PAD_INNER, 2), pady=2,
        )
        self._rollover_to_var = tk.StringVar(value="")
        self._rollover_combo = ttk.Combobox(
            parent, textvariable=self._rollover_to_var, values=fy_options,
            width=ENTRY_WIDTH, state="readonly", font=FONT_INPUT,
        )
        self._rollover_combo.grid(row=0, column=3, sticky="w", padx=(2, PAD_INNER), pady=2)

    def _build_buttons(self, parent):
        buttons = [
            ("Load Records",      self._on_load,     COLOR_PRIMARY),
            ("Refresh FY List",   self._on_refresh,  "#555555"),
            ("Rollover Year",     self._on_rollover, COLOR_SUCCESS),
            ("Delete FY Records", self._on_delete,   COLOR_WARNING),
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
            "asset_id", "asset_name", "asset_type",
            "it_open", "it_dep", "it_close",
            "ca_open", "ca_dep", "ca_close",
            "open_dta", "open_dtl", "dta", "dtl",
        )
        headings = (
            "Asset ID", "Asset Name", "Asset Type",
            "IT Opening WDV (₹)", "IT Dep (₹)", "IT Closing WDV (₹)",
            "CA Opening WDV (₹)", "CA Dep (₹)", "CA Closing WDV (₹)",
            "Opening DTA (₹)", "Opening DTL (₹)", "Closing DTA (₹)", "Closing DTL (₹)",
        )
        widths = (80, 150, 120, 110, 100, 110, 110, 100, 110, 100, 100, 100, 100)

        self._tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        for col, heading, w in zip(columns, headings, widths):
            self._tree.heading(col, text=heading)
            anchor = "w" if col in ("asset_name", "asset_type") else "e"
            self._tree.column(col, width=w, anchor=anchor, stretch=False)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._tree.tag_configure("even", background="#FFFFFF")
        self._tree.tag_configure("odd",  background=_ALT_COLOUR)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_load(self):
        fy = self._fy_var.get()
        records = db.get_history(fy)
        self._populate_table(records)
        log.info("Loaded %d history records for %s", len(records), fy)

    def _on_refresh(self):
        """Update the FY combo with years that have saved records."""
        saved_fys = db.list_financial_years()
        fy_options, _ = generate_fy_options()
        # Combine saved FYs with the standard options (no duplicates)
        combined = sorted(set(saved_fys) | set(fy_options))
        self._fy_combo.configure(values=combined)
        self._rollover_combo.configure(values=combined)
        log.info("FY list refreshed: %d options", len(combined))

    def _on_rollover(self):
        from_fy = self._fy_var.get()
        to_fy = self._rollover_to_var.get()
        if not to_fy:
            messagebox.showwarning("Rollover", "Please select a 'Rollover to' Financial Year.")
            return
        if from_fy == to_fy:
            messagebox.showwarning("Rollover", "Source and target financial years must differ.")
            return

        rolled = db.rollover_year(from_fy, to_fy)
        if not rolled:
            messagebox.showwarning(
                "Rollover",
                f"No records found for {from_fy}. Please save results first.",
            )
            return

        # Pre-load the rolled-over rows into the FAR Import tab if available
        if self._far_tab is not None:
            self._far_tab.load_rolled_over_rows(rolled, to_fy)
            messagebox.showinfo(
                "Rollover Complete",
                f"{len(rolled)} asset(s) rolled over from {from_fy} to {to_fy}.\n\n"
                "The FAR Import tab has been pre-loaded with the opening balances.\n"
                "Switch to that tab and click 'Calculate All' to process the new year.",
            )
        else:
            messagebox.showinfo(
                "Rollover Complete",
                f"{len(rolled)} asset(s) rolled over from {from_fy} to {to_fy}.",
            )

    def _on_delete(self):
        fy = self._fy_var.get()
        if not messagebox.askyesno(
            "Delete Records",
            f"Delete ALL saved records for {fy}?\nThis cannot be undone.",
        ):
            return
        n = db.delete_fy(fy)
        log.info("Deleted %d records for %s", n, fy)
        self._populate_table([])
        messagebox.showinfo("Deleted", f"{n} record(s) deleted for {fy}.")

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _populate_table(self, records: list):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for i, r in enumerate(records):
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end",
                values=(
                    r.get("asset_id", ""),
                    r.get("asset_name", ""),
                    r.get("asset_type", ""),
                    format_currency(r.get("it_opening_wdv", 0.0)),
                    format_currency(r.get("it_depreciation", 0.0)),
                    format_currency(r.get("it_closing_wdv", 0.0)),
                    format_currency(r.get("ca_opening_wdv", 0.0)),
                    format_currency(r.get("ca_depreciation", 0.0)),
                    format_currency(r.get("ca_closing_wdv", 0.0)),
                    format_currency(r.get("opening_dta", 0.0)),
                    format_currency(r.get("opening_dtl", 0.0)),
                    format_currency(r.get("dta", 0.0)),
                    format_currency(r.get("dtl", 0.0)),
                ),
                tags=(tag,),
            )

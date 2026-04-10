"""
ui/app.py — Main application window.

Assembles the ttk.Notebook with three tabs:
  1. Companies Act Depreciation
  2. Income Tax Depreciation
  3. DTA / DTL Calculator
"""

import tkinter as tk
from tkinter import ttk

from config import APP_TITLE, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
from ui.companies_act_tab import CompaniesActTab
from ui.income_tax_tab import IncomeTaxTab
from ui.dta_tab import DtaTab
from ui.styles import (
    COLOR_BG, COLOR_PRIMARY,
    FONT_LABEL,
)


def _apply_ttk_theme(root: tk.Tk):
    """
    Configure a clean, consistent ttk theme for the application.

    We base on the built-in 'clam' theme and override specific elements
    using styles defined in ui/styles.py.
    """
    style = ttk.Style(root)
    # 'clam' is available on all platforms and supports colour customisation
    available = style.theme_names()
    if "clam" in available:
        style.theme_use("clam")

    # Notebook tabs
    style.configure(
        "TNotebook.Tab",
        font=("Helvetica", 10, "bold"),
        padding=(12, 6),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_PRIMARY), ("active", "#5DADE2")],
        foreground=[("selected", "white"), ("active", "white")],
    )
    style.configure("TNotebook", background=COLOR_BG)

    # Frame
    style.configure("TFrame", background=COLOR_BG)
    style.configure("TLabelframe", background=COLOR_BG)
    style.configure("TLabelframe.Label", background=COLOR_BG, font=("Helvetica", 9, "bold"))

    # Label
    style.configure("TLabel", background=COLOR_BG, font=FONT_LABEL)

    # Entry
    style.configure("TEntry", fieldbackground="white")

    # Treeview
    style.configure(
        "Treeview.Heading",
        background=COLOR_PRIMARY,
        foreground="white",
        font=("Helvetica", 9, "bold"),
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", COLOR_PRIMARY)])
    style.configure("Treeview", rowheight=22, font=("Helvetica", 9))


class DepreciationApp:
    """
    Top-level application class.

    Creates the main window, applies the theme, and instantiates all tabs.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self._configure_window()
        _apply_ttk_theme(root)
        self._build_ui()

    def _configure_window(self):
        self.root.title(APP_TITLE)
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(bg=COLOR_BG)
        # Centre on screen
        w, h = MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1 — Companies Act
        ca_tab = CompaniesActTab(notebook)
        notebook.add(ca_tab, text="  Companies Act Depreciation  ")

        # Tab 2 — Income Tax
        it_tab = IncomeTaxTab(notebook)
        notebook.add(it_tab, text="  Tax Depreciation  ")

        # Tab 3 — DTA / DTL
        dta_tab = DtaTab(notebook)
        notebook.add(dta_tab, text="  DTA / DTL Calculator  ")

        # Wire cross-tab auto-fill:  CA → IT and DTA;  IT → DTA
        ca_tab.set_tax_tab(it_tab)
        ca_tab.set_dta_tab(dta_tab)
        it_tab.set_dta_tab(dta_tab)

    def run(self):
        """Start the tkinter event loop."""
        self.root.mainloop()

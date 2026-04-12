"""
ui/settings_tab.py — Application Settings tab.

Allows users to update:
  * Companies Act useful lives (years per category)
  * Income Tax depreciation rates (% per IT block)
  * DTA/DTL effective tax rates
  * Default residual value percentage

Changes are persisted to ``settings.json`` immediately and take effect on
the next calculation.  No recompile or restart is required.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from utils.app_settings import settings
from utils.logger import get_logger
from ui.styles import (
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING,
    FONT_HEADING, FONT_LABEL, FONT_INPUT, FONT_BUTTON, FONT_TITLE,
    PAD_OUTER, PAD_INNER, PAD_BUTTON,
)

log = get_logger(__name__)


class SettingsTab(ttk.Frame):
    """Tab for viewing and editing application configuration."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.configure(style="TFrame")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(padding=PAD_OUTER)

        ttk.Label(
            self,
            text="Application Settings",
            font=FONT_TITLE, foreground=COLOR_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, PAD_INNER))

        ttk.Label(
            self,
            text=(
                "Changes are saved to settings.json and take effect on the next calculation.\n"
                "No recompile or restart of the .exe is needed."
            ),
            font=FONT_LABEL, foreground="#555555",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, PAD_INNER * 2))

        # ── Companies Act useful lives ────────────────────────────────────────
        ca_frame = ttk.LabelFrame(self, text="Companies Act — Useful Lives (years)", padding=PAD_INNER)
        ca_frame.grid(row=2, column=0, sticky="nsew", padx=(0, PAD_INNER), pady=(0, PAD_INNER))
        self._ca_vars = self._build_kv_editor(ca_frame, settings.useful_lives, value_type="int")

        # ── Income Tax rates ──────────────────────────────────────────────────
        it_frame = ttk.LabelFrame(self, text="Income Tax — Depreciation Rates (%)", padding=PAD_INNER)
        it_frame.grid(row=2, column=1, sticky="nsew", padx=(PAD_INNER, 0), pady=(0, PAD_INNER))
        self._it_vars = self._build_kv_editor(it_frame, settings.it_rates, value_type="float")

        # ── DTA/DTL tax rates ─────────────────────────────────────────────────
        dta_frame = ttk.LabelFrame(self, text="DTA/DTL — Effective Tax Rates (%)", padding=PAD_INNER)
        dta_frame.grid(row=3, column=0, sticky="nsew", padx=(0, PAD_INNER), pady=(0, PAD_INNER))
        self._dta_vars = self._build_kv_editor(dta_frame, settings.dta_tax_rates, value_type="float")

        # ── Residual value ────────────────────────────────────────────────────
        misc_frame = ttk.LabelFrame(self, text="Miscellaneous", padding=PAD_INNER)
        misc_frame.grid(row=3, column=1, sticky="nsew", padx=(PAD_INNER, 0), pady=(0, PAD_INNER))
        self._residual_var = tk.StringVar(value=str(settings.residual_value_pct))
        ttk.Label(misc_frame, text="Default Residual Value (%):", font=FONT_LABEL).grid(
            row=0, column=0, sticky="e", padx=(0, 4), pady=2,
        )
        ttk.Entry(misc_frame, textvariable=self._residual_var, width=10, font=FONT_INPUT).grid(
            row=0, column=1, sticky="w", pady=2,
        )

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=PAD_INNER)
        tk.Button(
            btn_frame, text="Save Settings", command=self._on_save,
            bg=COLOR_SUCCESS, fg="white", font=FONT_BUTTON,
            relief="flat", padx=PAD_BUTTON, pady=4,
            activebackground=COLOR_SUCCESS, cursor="hand2",
        ).grid(row=0, column=0, padx=PAD_INNER)
        tk.Button(
            btn_frame, text="Reset to Defaults", command=self._on_reset,
            bg=COLOR_WARNING, fg="white", font=FONT_BUTTON,
            relief="flat", padx=PAD_BUTTON, pady=4,
            activebackground=COLOR_WARNING, cursor="hand2",
        ).grid(row=0, column=1, padx=PAD_INNER)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _build_kv_editor(self, parent, data: dict, value_type: str = "float") -> dict:
        """Build a two-column key–value editor inside *parent*.  Returns {key: StringVar}."""
        vars_map = {}
        for row_idx, (key, val) in enumerate(data.items()):
            ttk.Label(parent, text=key + ":", font=FONT_LABEL).grid(
                row=row_idx, column=0, sticky="e", padx=(0, 4), pady=2,
            )
            var = tk.StringVar(value=str(val))
            ttk.Entry(parent, textvariable=var, width=10, font=FONT_INPUT).grid(
                row=row_idx, column=1, sticky="w", pady=2,
            )
            vars_map[key] = (var, value_type)
        return vars_map

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _read_kv_vars(self, vars_map: dict) -> tuple:
        """Parse the key–value vars into a dict.  Returns (data_dict, errors)."""
        data = {}
        errors = []
        for key, (var, value_type) in vars_map.items():
            raw = var.get().strip()
            try:
                data[key] = int(raw) if value_type == "int" else float(raw)
            except ValueError:
                errors.append(f"'{key}': invalid value '{raw}'")
        return data, errors

    def _on_save(self):
        all_errors = []

        ca_data, ca_errors = self._read_kv_vars(self._ca_vars)
        all_errors.extend(ca_errors)

        it_data, it_errors = self._read_kv_vars(self._it_vars)
        all_errors.extend(it_errors)

        dta_data, dta_errors = self._read_kv_vars(self._dta_vars)
        all_errors.extend(dta_errors)

        try:
            residual = float(self._residual_var.get().strip())
        except ValueError:
            all_errors.append("'Default Residual Value (%)': invalid value")
            residual = None

        if all_errors:
            messagebox.showerror(
                "Validation Errors",
                "Please fix the following before saving:\n\n" + "\n".join(all_errors),
            )
            return

        settings.useful_lives = ca_data
        settings.it_rates = it_data
        settings.dta_tax_rates = dta_data
        if residual is not None:
            settings.residual_value_pct = residual

        if settings.save():
            log.info("Settings saved by user")
            messagebox.showinfo("Settings Saved", "Settings have been saved to settings.json.")
        else:
            messagebox.showerror("Save Error", "Could not write settings.json. Check file permissions.")

    def _on_reset(self):
        if not messagebox.askyesno(
            "Reset to Defaults",
            "This will reset ALL settings to their original defaults.\nContinue?",
        ):
            return

        import os
        if os.path.isfile(settings._path):
            try:
                os.remove(settings._path)
            except OSError as exc:
                log.error("Cannot remove settings.json: %s", exc)

        settings.reload()
        log.info("Settings reset to defaults")
        messagebox.showinfo(
            "Reset Complete",
            "Settings have been reset to defaults. Please switch away from and back to this tab to see the updated values.",
        )

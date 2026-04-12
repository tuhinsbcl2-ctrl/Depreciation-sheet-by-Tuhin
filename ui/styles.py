"""
ui/styles.py — Centralised style constants for the tkinter UI.

All colours, fonts, and padding values used across the application are
defined here to keep the visual identity consistent and easy to change.
"""

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
COLOR_PRIMARY = "#2E86AB"       # Blue — headers, buttons
COLOR_SECONDARY = "#A23B72"     # Purple — accent / DTA
COLOR_SUCCESS = "#27AE60"       # Green — positive values, export
COLOR_WARNING = "#E74C3C"       # Red — errors, warnings
COLOR_BG = "#F5F5F5"            # Light grey — window background
COLOR_FRAME_BG = "#FFFFFF"      # White — frame / card background
COLOR_TEXT = "#2C3E50"          # Dark charcoal — body text
COLOR_TEXT_LIGHT = "#7F8C8D"    # Grey — secondary / hint text
COLOR_HEADER_FG = "#FFFFFF"     # White text on coloured header rows
COLOR_ROW_ALT = "#EBF5FB"       # Alternating row tint (light blue)

# ---------------------------------------------------------------------------
# Fonts  (family, size, style)
# ---------------------------------------------------------------------------
FONT_TITLE = ("Helvetica", 14, "bold")
FONT_HEADING = ("Helvetica", 11, "bold")
FONT_LABEL = ("Helvetica", 10)
FONT_INPUT = ("Helvetica", 10)
FONT_BUTTON = ("Helvetica", 10, "bold")
FONT_TABLE = ("Courier", 9)
FONT_MONO  = ("Courier", 9)    # monospaced — error report dialogs, data tables
FONT_SMALL = ("Helvetica", 8)

# ---------------------------------------------------------------------------
# Padding / spacing
# ---------------------------------------------------------------------------
PAD_OUTER = 12      # outer frame padding (pixels)
PAD_INNER = 6       # inner widget spacing
PAD_BUTTON = 8      # button horizontal padding

# ---------------------------------------------------------------------------
# Widget sizing
# ---------------------------------------------------------------------------
ENTRY_WIDTH = 20    # default width (characters) for Entry widgets
BUTTON_WIDTH = 16   # default button width

# ---------------------------------------------------------------------------
# Treeview
# ---------------------------------------------------------------------------
TREE_ROW_HEIGHT = 22
TREE_HEADER_BG = COLOR_PRIMARY
TREE_HEADER_FG = COLOR_HEADER_FG

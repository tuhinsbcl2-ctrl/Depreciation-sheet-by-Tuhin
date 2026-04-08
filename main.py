"""
main.py — Entry point for the Depreciation & DTA/DTL Calculator application.

Usage
-----
    python main.py

Requirements
------------
    pip install -r requirements.txt
"""

import tkinter as tk

from ui.app import DepreciationApp


def main():
    """Create the root window and start the application."""
    root = tk.Tk()
    app = DepreciationApp(root)
    app.run()


if __name__ == "__main__":
    main()

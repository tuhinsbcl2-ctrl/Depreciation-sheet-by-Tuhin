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

from utils.logger import setup_logging, get_logger
from ui.app import DepreciationApp

# Initialise logging before anything else so all modules can write to app.log
setup_logging()
log = get_logger(__name__)


def main():
    """Create the root window and start the application."""
    log.info("Application starting")
    try:
        root = tk.Tk()
        app = DepreciationApp(root)
        app.run()
    except Exception as exc:
        log.exception("Unhandled exception in main: %s", exc)
        raise
    finally:
        log.info("Application exiting")


if __name__ == "__main__":
    main()

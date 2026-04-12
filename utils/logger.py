"""
utils/logger.py — Application-wide logging setup.

Writes INFO and above to ``app.log`` in the same directory as the executable
(or the repository root when running from source).  Errors are also printed
to stderr so they are visible in development.

Usage
-----
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Application started")
    log.error("Something went wrong: %s", exc)
"""

import logging
import os
import sys


def _log_dir() -> str:
    """
    Return the directory where ``app.log`` should be written.

    When packaged as a PyInstaller executable, ``sys.executable`` points to
    the ``.exe``; otherwise we use the directory that contains ``main.py``
    (i.e. the repository root).
    """
    if getattr(sys, "frozen", False):
        # Running as a bundled .exe
        return os.path.dirname(sys.executable)
    # Running from source — place the log next to main.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure the root logger with a file handler (``app.log``) and a stderr
    stream handler.  Safe to call multiple times — subsequent calls are no-ops.
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — always write to app.log
    log_path = os.path.join(_log_dir(), "app.log")
    try:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # Can't write to the log directory — degrade gracefully

    # Console handler — useful during development / debugging
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring the root logger is configured first."""
    setup_logging()
    return logging.getLogger(name)

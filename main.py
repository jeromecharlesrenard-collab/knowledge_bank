"""JCR Knowledge Bank - entry point.

Sets up logging, loads config.json, and launches the local preview
(hidden web server; add --window for the control window). Runs under pythonw.exe with no console.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def main() -> None:
    """Start the local preview."""
    os.chdir(PROJECT_DIR)
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))
    try:
        from tools.kb_core import log, start
        from tools.preview import run
    except Exception:  # noqa: BLE001 - fails before logging is ready
        details = traceback.format_exc()
        (PROJECT_DIR / "error_log.txt").write_text(details, encoding="utf-8")
        try:
            import tkinter as tk
            from tkinter import messagebox

            tk.Tk().withdraw()
            messagebox.showerror("JCR Knowledge Bank - Startup Error", details)
        finally:
            raise SystemExit(1)

    config = start(show_dialog=True)
    log.info("Startup: JCR Knowledge Bank preview")
    try:
        run(config, window="--window" in sys.argv[1:])
    finally:
        log.info("Shutdown")


if __name__ == "__main__":
    main()

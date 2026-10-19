"""Shared helpers: project paths, config loading, logging, and error handling."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any

PROJECT_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = PROJECT_DIR / "config.json"
LOG_DIR: Path = PROJECT_DIR / "logs"
LOG_FILE: Path = LOG_DIR / "app.log"
ERROR_LOG: Path = PROJECT_DIR / "error_log.txt"

DEFAULT_CONFIG: dict[str, Any] = {
    "log_level": "INFO",
    "preview_port": 8000,
    "preview_idle_minutes": 60,
    "site_url": "https://jeromecharlesrenard-collab.github.io/knowledge_bank/",
    "repo_url": "https://github.com/jeromecharlesrenard-collab/knowledge_bank",
    "default_source": "JCR research",
}

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(module)s | %(message)s"

log = logging.getLogger("knowledge_bank")


def load_config() -> dict[str, Any]:
    """Return settings from config.json merged over the defaults."""
    config = dict(DEFAULT_CONFIG)
    try:
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except FileNotFoundError:
        log.warning("config.json not found, using defaults")
    except json.JSONDecodeError as exc:
        log.error("config.json is not valid JSON (%s), using defaults", exc)
    return config


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the rotating log file logs/app.log (1 MB x 5 files)."""
    LOG_DIR.mkdir(exist_ok=True)
    root = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    return log


def write_error_log(text: str) -> None:
    """Last-resort error report, used when logging is not available."""
    try:
        ERROR_LOG.write_text(text, encoding="utf-8")
    except OSError:
        pass


def show_error_box(title: str, message: str) -> None:
    """Show an error message box without depending on a console."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001 - nothing else we can do
        pass


def install_excepthook(show_dialog: bool = False) -> None:
    """Log every uncaught exception; optionally show it in a dialog."""

    def hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        log.critical("Uncaught exception:\n%s", details)
        if show_dialog:
            show_error_box("JCR Knowledge Bank - Error", f"{exc_type.__name__}: {exc}\n\nDetails are in logs\\app.log")
        else:
            sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def start(show_dialog: bool = False) -> dict[str, Any]:
    """Standard startup for every tool: config, logging, exception hook."""
    try:
        config = load_config()
        setup_logging(config.get("log_level", "INFO"))
        install_excepthook(show_dialog)
        return config
    except Exception:  # noqa: BLE001 - failure before logging is ready
        details = traceback.format_exc()
        write_error_log(details)
        show_error_box("JCR Knowledge Bank - Startup Error", details)
        raise

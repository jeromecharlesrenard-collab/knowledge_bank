"""Local preview of the website, behaving like GitHub Pages.

Starts a web server at http://localhost:<preview_port> (config.json) and opens the
home page in the default browser. Unlike a plain Windows file server, it rejects
links whose upper/lowercase does not match the actual file, exactly like GitHub.
Pages are never cached, so a normal refresh shows your latest edits.

A small control window shows the address and offers OPEN SITE / CHECK SITE / EXIT.
Closing the window (or Esc) stops the server.

Usage:  .venv\\Scripts\\pythonw.exe main.py   (or the knowledge_bank shortcut)
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox
from typing import Any

from tools.kb_core import PROJECT_DIR, log
from tools.site_check import check_site, resolve_exact

FONT = "Arial"
GREEN = "#1a7f37"
BLUE = "#0b57d0"


class GitHubLikeHandler(SimpleHTTPRequestHandler):
    """Static file handler with case-sensitive paths and no caching."""

    def send_head(self):  # type: ignore[override]
        path = Path(self.translate_path(self.path))
        if path.exists() and resolve_exact(Path(self.directory), path) == "case":
            self.send_error(404, "File not found (upper/lowercase differs, as GitHub Pages would report)")
            return None
        return super().send_head()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base class signature
        log.debug("HTTP %s", format % args)


def start_server(root: Path, port: int, attempts: int = 10) -> ThreadingHTTPServer:
    """Start the server in a background thread, trying the next ports if busy."""
    handler = partial(GitHubLikeHandler, directory=str(root))
    for candidate in range(port, port + attempts):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError:
            log.info("Port %d busy, trying the next one", candidate)
            continue
        threading.Thread(target=server.serve_forever, daemon=True, name="preview-server").start()
        log.info("Preview server started on http://localhost:%d/", candidate)
        return server
    raise OSError(f"No free port between {port} and {port + attempts - 1}")


class PreviewWindow:
    """Small control window for the preview server."""

    def __init__(self, root: tk.Tk, server: ThreadingHTTPServer) -> None:
        self.root = root
        self.server = server
        self.url = f"http://localhost:{server.server_address[1]}/"

        root.title("knowledge_bank")
        root.configure(bg="white")
        icon = PROJECT_DIR / "assets" / "knowledge_bank.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
        width, height = 560, 300
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 3
        root.geometry(f"{width}x{height}+{x}+{y}")
        root.resizable(False, False)

        title = tk.Frame(root, bg="white")
        title.pack(pady=(28, 6))
        tk.Label(title, text="JCR KNOWLEDGE BANK ", font=("Arial Black", 18), bg="white", fg="black").pack(side="left")
        tk.Label(title, text="PREVIEW", font=("Arial Black", 18), bg="white", fg=BLUE).pack(side="left")

        tk.Label(root, text="Site running at", font=(FONT, 11), bg="white").pack(pady=(10, 0))
        link = tk.Label(root, text=self.url, font=(FONT, 13, "bold underline"), bg="white", fg=BLUE, cursor="hand2")
        link.pack()
        link.bind("<Button-1>", lambda _e: self.open_site())

        self.status = tk.Label(root, text="Ready", font=(FONT, 11), bg="white", fg=GREEN)
        self.status.pack(pady=(18, 6))

        buttons = tk.Frame(root, bg="white")
        buttons.pack(pady=(0, 16))
        self.open_btn = self._button(buttons, "OPEN SITE", self.open_site)
        self.check_btn = self._button(buttons, "CHECK SITE", self.check)
        self._button(buttons, "EXIT", self.exit)

        root.protocol("WM_DELETE_WINDOW", self.exit)
        root.bind("<Escape>", lambda _e: self.exit())
        root.bind("<Return>", lambda _e: self.open_site())
        root.report_callback_exception = self._callback_error  # type: ignore[assignment]

    def _button(self, parent: tk.Frame, text: str, command: Any) -> tk.Button:
        btn = tk.Button(parent, text=text, command=command, font=(FONT, 10, "bold"), width=12,
                        bg="white", fg="black", relief="solid", bd=1, cursor="hand2")
        btn.pack(side="left", padx=8)
        return btn

    def _callback_error(self, exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        log.error("Window callback error", exc_info=(exc_type, exc, tb))
        messagebox.showerror("Error", f"{exc}\n\nDetails are in logs\\app.log", parent=self.root)

    def open_site(self) -> None:
        log.info("User: OPEN SITE")
        webbrowser.open(self.url)
        self.status.config(text="Opened the home page in your browser")

    def check(self) -> None:
        log.info("User: CHECK SITE")
        self.check_btn.config(state="disabled")
        self.status.config(text="Checking pages, links, and images...")
        threading.Thread(target=self._run_check, daemon=True, name="site-check").start()

    def _run_check(self) -> None:
        try:
            issues = check_site()
            error = None
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("Site check failed")
            issues, error = [], exc
        self.root.after(0, self._show_check, issues, error)

    def _show_check(self, issues: list[Any], error: Exception | None) -> None:
        self.check_btn.config(state="normal")
        if error:
            self.status.config(text="Site check failed")
            messagebox.showerror("Site Check", f"{error}\n\nDetails are in logs\\app.log", parent=self.root)
        elif issues:
            self.status.config(text=f"Site check: {len(issues)} problem(s) found")
            shown = "\n".join(f"- {i}" for i in issues[:20])
            more = f"\n... and {len(issues) - 20} more (see logs\\app.log)" if len(issues) > 20 else ""
            for issue in issues:
                log.warning("Site check: %s", issue)
            messagebox.showwarning("Site Check", f"{len(issues)} problem(s) found:\n\n{shown}{more}", parent=self.root)
        else:
            self.status.config(text="Site check: all good, no problems found")

    def exit(self) -> None:
        log.info("User: EXIT, stopping preview server")
        threading.Thread(target=self.server.shutdown, daemon=True).start()
        self.root.destroy()


def run(config: dict[str, Any]) -> None:
    """Start the server, open the browser, and show the control window."""
    root = tk.Tk()
    root.withdraw()
    try:
        server = start_server(PROJECT_DIR, int(config.get("preview_port", 8000)))
    except OSError as exc:
        log.error("Preview server could not start: %s", exc)
        messagebox.showerror("Preview", f"The preview server could not start:\n{exc}")
        root.destroy()
        return
    window = PreviewWindow(root, server)
    root.deiconify()
    root.after(200, window.open_site)
    root.mainloop()
    server.server_close()
    log.info("Preview stopped")


if __name__ == "__main__":
    from tools.kb_core import start

    os.chdir(PROJECT_DIR)
    run(start(show_dialog=True))

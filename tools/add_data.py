"""ADD KB DATA: add a source file or pasted text to a knowledge page.

A window (same style as the PREVIEW window) collects:
  - the target page (drop-down list of the pages on the home page)
  - a source file (text, Word .docx, PDF, or image), and/or
  - pasted text
PROCESS prepares the material, then hands the placement to Claude Code
(`claude -p`, run in the project folder so CLAUDE.md applies). Claude puts each
piece of information in the right place on the page, or in a new section in the
page style, runs the site check and tests, then commits and pushes to GitHub.

Preparation done here, before Claude runs:
  - images are copied into kb_images/ as <page>_<name>.<ext>
  - Word documents are converted to text (bold kept as **...**, tables as rows);
    their embedded pictures are copied into kb_images/ too
  - other files are copied into logs/add_data/ (git-ignored) for Claude to read

Usage:  .venv\\Scripts\\pythonw.exe main.py --add-data   (or the ADD KB DATA shortcut)
"""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from tools.kb_core import PROJECT_DIR, log

FONT = "Arial"
GREEN = "#1a7f37"
BLUE = "#0b57d0"
RED = "#b3261e"

WORK_DIR_NAME = Path("logs") / "add_data"
TEXT_TYPES = {".txt", ".md", ".csv", ".json", ".html", ".htm"}
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
WORD_TYPES = {".docx"}
PDF_TYPES = {".pdf"}
SUPPORTED_TYPES = TEXT_TYPES | IMAGE_TYPES | WORD_TYPES | PDF_TYPES

ENTRY_LINK = re.compile(r'<a href="(html_pages/[^"]+\.html)"[^>]*>\s*<span class="name">(.*?)</span>', re.S)
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Claude may only edit files, run the site check and tests, and use git to publish.
ALLOWED_TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(.venv/Scripts/python.exe -m tools.site_check:*)",
    "Bash(.venv/Scripts/python.exe -m pytest:*)",
    "Bash(.venv\\Scripts\\python.exe -m tools.site_check:*)",
    "Bash(.venv\\Scripts\\python.exe -m pytest:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
    "Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)",
]


@dataclass
class Page:
    """A knowledge page listed on the home page."""

    name: str
    path: str  # relative to the project folder, e.g. "html_pages/Tesla.html"


@dataclass
class Material:
    """Prepared input for Claude: prompt lines and the images already copied."""

    lines: list[str] = field(default_factory=list)
    images: list[Path] = field(default_factory=list)


# ---------- Logic (tested in tests/test_add_data.py) ----------

def list_pages(root: Path = PROJECT_DIR) -> list[Page]:
    """Return the pages listed on index.html, sorted by name."""
    text = (root / "index.html").read_text(encoding="utf-8")
    pages = [Page(html.unescape(re.sub(r"<[^>]+>", "", name)).strip(), href)
             for href, name in ENTRY_LINK.findall(text)]
    return sorted(pages, key=lambda p: p.name.lower())


def safe_name(text: str) -> str:
    """Lowercase file-name stem with only letters, digits, and underscores."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "image"


def unique_path(folder: Path, filename: str) -> Path:
    """Return folder/filename, adding _2, _3, ... if that file already exists."""
    target = folder / filename
    stem, suffix = target.stem, target.suffix
    n = 2
    while target.exists():
        target = folder / f"{stem}_{n}{suffix}"
        n += 1
    return target


def image_target(root: Path, page: Page, source_name: str) -> Path:
    """Where an image for this page goes: kb_images/<page>_<name>.<ext>."""
    prefix = safe_name(Path(page.path).stem)
    name = Path(source_name)
    stem = safe_name(name.stem)
    filename = f"{prefix}_{stem}{name.suffix.lower()}" if not stem.startswith(prefix) else f"{stem}{name.suffix.lower()}"
    folder = root / "kb_images"
    folder.mkdir(exist_ok=True)
    return unique_path(folder, filename)


def _paragraph_text(paragraph: ET.Element) -> str:
    """Text of one Word paragraph, with bold runs marked **...**."""
    parts: list[str] = []
    for run in paragraph.iter(f"{W_NS}r"):
        text = ""
        for node in run:
            if node.tag == f"{W_NS}t":
                text += node.text or ""
            elif node.tag == f"{W_NS}tab":
                text += "\t"
            elif node.tag in (f"{W_NS}br", f"{W_NS}cr"):
                text += "\n"
        bold = run.find(f"{W_NS}rPr/{W_NS}b")
        is_bold = bold is not None and bold.get(f"{W_NS}val", "true") not in ("0", "false")
        parts.append(f"**{text.strip()}** " if is_bold and text.strip() else text)
    line = "".join(parts).strip()
    if line and paragraph.find(f"{W_NS}pPr/{W_NS}numPr") is not None:
        line = f"- {line}"
    return line


def docx_to_text(path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    """Return the text of a .docx (tables as 'a | b' rows) and its embedded pictures."""
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        media = [(Path(n).name, archive.read(n)) for n in archive.namelist() if n.startswith("word/media/")]
    body = document.find(f"{W_NS}body")
    lines: list[str] = []
    for element in body if body is not None else []:
        if element.tag == f"{W_NS}p":
            lines.append(_paragraph_text(element))
        elif element.tag == f"{W_NS}tbl":
            for row in element.iter(f"{W_NS}tr"):
                cells = [" ".join(_paragraph_text(p) for p in cell.iter(f"{W_NS}p")).strip()
                         for cell in row.findall(f"{W_NS}tc")]
                lines.append(" | ".join(cells))
            lines.append("")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text, media


def prepare_material(page: Page, file: Path | None, text: str, root: Path = PROJECT_DIR) -> Material:
    """Copy or convert the inputs and describe them for the prompt."""
    material = Material()
    work = root / WORK_DIR_NAME
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    if file is not None:
        suffix = file.suffix.lower()
        if suffix not in SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type '{suffix}'. Use: {', '.join(sorted(SUPPORTED_TYPES))}")
        if not file.is_file():
            raise FileNotFoundError(f"File not found: {file}")
        if suffix in IMAGE_TYPES:
            target = image_target(root, page, file.name)
            shutil.copy2(file, target)
            material.images.append(target)
            material.lines.append(f"- Source image '{file.name}', already copied to "
                                  f"kb_images/{target.name} (link it as ../kb_images/{target.name}).")
        elif suffix in WORD_TYPES:
            doc_text, media = docx_to_text(file)
            converted = work / f"{safe_name(file.stem)}.txt"
            converted.write_text(doc_text, encoding="utf-8")
            material.lines.append(f"- Source Word document '{file.name}', converted to text in "
                                  f"{converted.relative_to(root).as_posix()} (bold kept as **...**).")
            for name, data in media:
                target = image_target(root, page, f"{file.stem}_{name}")
                target.write_bytes(data)
                material.images.append(target)
                material.lines.append(f"- Picture from the document, already copied to kb_images/{target.name} "
                                      f"(link it as ../kb_images/{target.name}).")
        else:
            copied = work / file.name
            shutil.copy2(file, copied)
            kind = "PDF" if suffix in PDF_TYPES else "text file"
            material.lines.append(f"- Source {kind} '{file.name}', copied to {copied.relative_to(root).as_posix()}.")

    if text.strip():
        material.lines.append("- Text typed or pasted by the user, between the markers:\n"
                              "<<<USER TEXT\n" + text.strip() + "\nUSER TEXT>>>")

    if not material.lines:
        raise ValueError("Nothing to add: choose a source file or enter text.")
    return material


def build_prompt(page: Page, material: Material, today: date | None = None) -> str:
    """The instructions given to Claude for this job."""
    day = (today or date.today()).isoformat()
    images = (f"\n- {len(material.images)} image(s) were copied into kb_images/. Show each one where it belongs, "
              "in the page style, with alt text. If an image is not useful on the page, do not show it, and "
              "say so in your report." if material.images else "")
    return f"""You are updating the JCR Knowledge Bank website in this folder. Follow CLAUDE.md exactly.

TASK: add the new material below to the page "{page.name}" ({page.path}).

How to do it:
- Read {page.path} and its sections first, then read the material.
- Put each piece of information where it logically belongs: extend the matching box, row, table, or list,
  keeping the page's existing order (chronological, by size, etc.). If nothing fits, create a new section
  or box in the page's existing style (same classes, expand function, etc.).
- Never duplicate facts already on the page. If the material updates a fact, replace the old value.
- Keep it clean, short, and concise, like a quick reference. American spelling. Bold key terms the way the
  page does. No <style> blocks, no numbering badges. Add a shared class to assets/kb_style.css only if needed.
- Check the facts. Correct clear errors and list every correction in your report. Do not invent content.
- Pages must not link to data/ or logs/.{images}
- Update the footer date ("updated {day}"). If the page's scope changed, update its header description and
  the matching description on index.html.
- Then run: .venv/Scripts/python.exe -m tools.site_check  and  .venv/Scripts/python.exe -m pytest -q
  Fix any problem they report. Then git add only the files you changed (including new kb_images files),
  git commit with a short message, and git push origin main.
- If the material does not fit this page at all, or cannot be read, change nothing and explain why.

Finish with a short plain-text report for the user (no tables): what was added and where, any corrections,
and whether it was published.

MATERIAL:
""" + "\n".join(material.lines) + "\n"


def find_claude() -> str:
    """Path of the Claude Code command line."""
    found = shutil.which("claude")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "claude.exe"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError("Claude Code (claude.exe) was not found. Install it or add it to PATH.")


def claude_args(executable: str) -> list[str]:
    """Command line for a non-interactive Claude run (the prompt goes to stdin)."""
    return [executable, "-p", "--output-format", "text", "--permission-mode", "acceptEdits",
            "--allowedTools", *ALLOWED_TOOLS]


# ---------- Window ----------

class AddDataWindow:
    """The ADD KB DATA window."""

    def __init__(self, root: tk.Tk, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self.started = 0.0
        self.pages: list[Page] = []

        root.title("knowledge_bank - add data")
        root.configure(bg="white")
        icon = PROJECT_DIR / "assets" / "knowledge_bank.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
        width = 900
        root.resizable(False, False)
        root.option_add("*TCombobox*Listbox.font", (FONT, 10))

        title = tk.Frame(root, bg="white")
        title.pack(pady=(18, 10))
        tk.Label(title, text="JCR KNOWLEDGE BANK ", font=("Arial Black", 18), bg="white", fg="black").pack(side="left")
        tk.Label(title, text="ADD DATA", font=("Arial Black", 18), bg="white", fg=BLUE).pack(side="left")

        # Everything sits in a column 80% of the window width (10% margin each side).
        body = tk.Frame(root, bg="white", width=int(width * 0.8))
        body.pack(fill="x", padx=int(width * 0.1))
        body.columnconfigure(1, weight=1)

        self._label(body, "Target page", 0)
        page_row = tk.Frame(body, bg="white")
        page_row.grid(row=0, column=1, sticky="ew", pady=4)
        self.page_var = tk.StringVar()
        self.page_box = ttk.Combobox(page_row, textvariable=self.page_var, state="readonly", font=(FONT, 10))
        self.page_box.pack(side="left", fill="x", expand=True)
        self.view_btn = self._small_button(page_row, "VIEW", self.view_page)

        self._label(body, "Source file", 1)
        file_row = tk.Frame(body, bg="white")
        file_row.grid(row=1, column=1, sticky="ew", pady=4)
        self.file_var = tk.StringVar()
        self.file_entry = tk.Entry(file_row, textvariable=self.file_var, font=(FONT, 10), relief="solid", bd=1)
        self.file_entry.pack(side="left", fill="x", expand=True, ipady=2)
        self.browse_btn = self._small_button(file_row, "BROWSE", self.browse)

        self._label(body, "or Text", 2)
        text_frame = tk.Frame(body, bg="white", relief="solid", bd=1)
        text_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.text = tk.Text(text_frame, height=20, font=(FONT, 10), wrap="word", relief="flat", bd=4, undo=True)
        scroll = tk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.status = tk.Label(body, text="Choose a page, then a source file or text.", font=(FONT, 10),
                               bg="white", fg=GREEN, wraplength=int(width * 0.8), justify="center")
        self.status.grid(row=4, column=0, columnspan=2, pady=(10, 6))

        buttons = tk.Frame(body, bg="white")
        buttons.grid(row=5, column=0, columnspan=2, pady=(0, 16))
        self.process_btn = self._button(buttons, "PROCESS", self.process_data)
        self._button(buttons, "EXIT", self.exit)

        # Size to the content, centered on the screen.
        root.update_idletasks()
        height = root.winfo_reqheight()
        x = (root.winfo_screenwidth() - width) // 2
        y = max(0, (root.winfo_screenheight() - height) // 2 - 20)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.protocol("WM_DELETE_WINDOW", self.exit)
        root.bind("<Escape>", lambda _e: self.exit())
        root.report_callback_exception = self._callback_error  # type: ignore[assignment]
        self.load_pages()

    # ----- widgets -----

    def _label(self, parent: tk.Frame, text: str, row: int, sticky: str = "w") -> None:
        tk.Label(parent, text=text, font=(FONT, 11, "bold"), bg="white").grid(row=row, column=0, sticky=sticky,
                                                                            padx=(0, 12), pady=6)

    def _button(self, parent: tk.Frame, text: str, command: Any) -> tk.Button:
        btn = tk.Button(parent, text=text, command=command, font=(FONT, 10, "bold"), width=12,
                        bg="white", fg="black", relief="solid", bd=1, cursor="hand2")
        btn.pack(side="left", padx=8)
        return btn

    def _small_button(self, parent: tk.Frame, text: str, command: Any) -> tk.Button:
        btn = tk.Button(parent, text=text, command=command, font=(FONT, 9, "bold"), width=8,
                        bg="white", fg="black", relief="solid", bd=1, cursor="hand2")
        btn.pack(side="left", padx=(8, 0))
        return btn

    def _callback_error(self, exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        log.error("Window callback error", exc_info=(exc_type, exc, tb))
        messagebox.showerror("Error", f"{exc}\n\nDetails are in logs\\app.log", parent=self.root)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for widget in (self.process_btn, self.browse_btn, self.file_entry, self.view_btn):
            widget.config(state=state)
        self.page_box.config(state="disabled" if busy else "readonly")
        self.text.config(state=state)

    # ----- actions -----

    def load_pages(self) -> None:
        self.pages = list_pages()
        self.page_box["values"] = [p.name for p in self.pages]
        log.info("Add data: %d page(s) listed", len(self.pages))

    def selected_page(self) -> Page | None:
        name = self.page_var.get()
        return next((p for p in self.pages if p.name == name), None)

    def view_page(self) -> None:
        page = self.selected_page()
        if page is None:
            self.status.config(text="Choose a target page first.", fg=RED)
            return
        webbrowser.open(self.config["site_url"].rstrip("/") + "/" + page.path)

    def browse(self) -> None:
        start = PROJECT_DIR / "data"
        kinds = " ".join(f"*{s}" for s in sorted(SUPPORTED_TYPES))
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose the source file",
                                            initialdir=str(start if start.exists() else PROJECT_DIR),
                                            filetypes=[("Supported files", kinds), ("All files", "*.*")])
        if chosen:
            self.file_var.set(str(Path(chosen)))

    def process_data(self) -> None:
        page = self.selected_page()
        file_text = self.file_var.get().strip().strip('"')
        text = self.text.get("1.0", "end").strip()
        if page is None:
            self.status.config(text="Choose a target page first.", fg=RED)
            return
        if not file_text and not text:
            self.status.config(text="Choose a source file or enter text.", fg=RED)
            return
        file = Path(file_text) if file_text else None
        if file is not None and not file.is_file():
            self.status.config(text=f"File not found: {file}", fg=RED)
            return
        log.info("User: PROCESS page=%s file=%s text=%d chars", page.path, file, len(text))
        self._set_busy(True)
        self.started = time.monotonic()
        self._tick()
        threading.Thread(target=self._run_job, args=(page, file, text), daemon=True, name="add-data").start()

    def _tick(self) -> None:
        if self.started == 0.0:
            return
        elapsed = int(time.monotonic() - self.started)
        self.status.config(text=f"Working... {elapsed // 60}:{elapsed % 60:02d}  Claude is placing the data, "
                                "checking, and publishing (usually 1 to 5 minutes).", fg=BLUE)
        self.root.after(1000, self._tick)

    def _run_job(self, page: Page, file: Path | None, text: str) -> None:
        try:
            material = prepare_material(page, file, text)
            prompt = build_prompt(page, material)
            args = claude_args(find_claude())
            timeout = float(self.config.get("add_data_timeout_minutes", 20)) * 60
            log.info("Add data: starting Claude for %s", page.path)
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(args, cwd=PROJECT_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                            creationflags=flags)
            try:
                out, err = self.process.communicate(prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                out, err = self.process.communicate()
                raise TimeoutError(f"Claude did not finish within {timeout / 60:.0f} minutes.") from None
            code = self.process.returncode
            self.process = None
            log.info("Add data: Claude finished with code %s", code)
            if out:
                log.info("Add data report:\n%s", out.strip())
            if code != 0:
                raise RuntimeError((err or out or f"Claude exited with code {code}").strip())
            self._post(self._done, page, out.strip() or "Done.", None)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("Add data failed")
            self.process = None
            self._post(self._done, page, "", exc)

    def _post(self, *args: Any) -> None:
        """Run a callback on the window thread, unless the window was closed."""
        try:
            self.root.after(0, *args)
        except (RuntimeError, tk.TclError):
            log.info("Add data: window closed before the job finished")

    def _done(self, page: Page, report: str, error: Exception | None) -> None:
        self.started = 0.0
        self._set_busy(False)
        if error:
            self.status.config(text="Not added. See the message for details.", fg=RED)
            messagebox.showerror("Add Data", f"{error}\n\nDetails are in logs\\app.log", parent=self.root)
            return
        self.status.config(text=f"Done: {page.name}. The live page updates in 1 to 2 minutes.", fg=GREEN)
        self.file_var.set("")
        self.text.delete("1.0", "end")
        ResultWindow(self.root, page, report, self.config["site_url"])

    def exit(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno("Add Data", "A job is still running. Stop it and exit?", parent=self.root):
                return
            log.info("User: EXIT, stopping the running job")
            self.process.kill()
        log.info("User: EXIT")
        self.root.destroy()


class ResultWindow:
    """Shows Claude's report after a job."""

    def __init__(self, parent: tk.Tk, page: Page, report: str, site_url: str) -> None:
        win = tk.Toplevel(parent, bg="white")
        win.title("knowledge_bank - result")
        win.geometry(f"720x480+{parent.winfo_rootx() + 90}+{parent.winfo_rooty() + 80}")
        icon = PROJECT_DIR / "assets" / "knowledge_bank.ico"
        if icon.exists():
            win.iconbitmap(str(icon))
        tk.Label(win, text=f"RESULT: {page.name.upper()}", font=("Arial Black", 14), bg="white").pack(pady=(18, 10))
        frame = tk.Frame(win, bg="white", relief="solid", bd=1)
        frame.pack(fill="both", expand=True, padx=24)
        text = tk.Text(frame, font=(FONT, 11), wrap="word", relief="flat", bd=6)
        scroll = tk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.insert("1.0", report)
        text.config(state="disabled")
        buttons = tk.Frame(win, bg="white")
        buttons.pack(pady=14)
        url = site_url.rstrip("/") + "/" + page.path
        for label, command in (("VIEW PAGE", lambda: webbrowser.open(url)), ("CLOSE", win.destroy)):
            tk.Button(buttons, text=label, command=command, font=(FONT, 10, "bold"), width=12, bg="white",
                      fg="black", relief="solid", bd=1, cursor="hand2").pack(side="left", padx=8)
        win.bind("<Escape>", lambda _e: win.destroy())


def run(config: dict[str, Any]) -> None:
    """Open the ADD KB DATA window."""
    root = tk.Tk()
    AddDataWindow(root, config)
    root.mainloop()


if __name__ == "__main__":
    from tools.kb_core import start

    os.chdir(PROJECT_DIR)
    run(start(show_dialog=True))

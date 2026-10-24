"""KNOWLEDGE BANK ADD DATA: add a source file, text, or instructions to a knowledge page.

A maximized window (same style as the Chart Price Plot app) collects:
  - the target page (drop-down list of the pages on the home page)
  - a source file (.docx, .pdf, .txt, .xlsx, .jpg, .png, .html), and/or pasted text
  - instructions (how or where to add the data, or edits to make), applied by Claude
  - "Update GitHub" (checked by default) and "Match GitHub" (unchecked by default)
PROCESS prepares the material, then hands the work to Claude Code
(`claude -p`, run in the project folder so CLAUDE.md applies). Claude carries out
the instructions, puts each piece of information in the right place on the page
(or in a new section in the page style), and runs the site check and tests.
  - Update GitHub checked: Claude also commits and pushes.
  - Unchecked: only the local files change; a pop-up then offers to publish.
    Publishing from the pop-up commits only the files this job changed.
  - Match GitHub checked: no page work. Every local change not yet on GitHub
    (edits, new and deleted files, unpushed commits) is checked, committed, and
    pushed, so GitHub matches the local knowledge bank exactly.

Preparation done here, before Claude runs:
  - images are copied into kb_images/ as <page>_<name>.<ext>
  - Word documents are converted to text (bold kept as **...**, tables as rows);
    their embedded pictures are copied into kb_images/ too
  - Excel workbooks are converted to text (one block per sheet, cells as rows)
  - PDF, text, and HTML files are copied into logs/add_data/ (git-ignored) for Claude to read

Usage:  .venv\\Scripts\\pythonw.exe main.py --add-data   (or the KNOWLEDGE BANK ADD shortcut)
"""

from __future__ import annotations

import hashlib
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
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any

from tools.kb_core import PROJECT_DIR, log

# Chart Price Plot look
WHITE = "#FFFFFF"
TEXT_COLOR = "#000000"
GRAY = "#444444"
TITLE_FONT = ("Segoe UI", 20, "bold")
SUBTITLE_FONT = ("Segoe UI", 10)
LABEL_FONT = ("Segoe UI", 12)
ENTRY_FONT = ("Segoe UI", 12)
TEXT_FONT = ("Segoe UI", 10)
SMALL_FONT = ("Segoe UI", 10)
BUTTON_FONT = ("Segoe UI", 9, "bold")
STATUS_FONT = ("Segoe UI", 10)
GREEN = "#0a6b1a"
BLUE = "#0b57d0"
RED = "#b3261e"
TEXT_WIDTH = 0.8  # instruction and text boxes: 80% of the window width

WORK_DIR_NAME = Path("logs") / "add_data"
TEXT_TYPES = {".txt", ".html", ".htm"}
IMAGE_TYPES = {".jpg", ".jpeg", ".png"}
WORD_TYPES = {".docx"}
EXCEL_TYPES = {".xlsx"}
PDF_TYPES = {".pdf"}
SUPPORTED_TYPES = TEXT_TYPES | IMAGE_TYPES | WORD_TYPES | EXCEL_TYPES | PDF_TYPES

ENTRY_LINK = re.compile(r'<a href="(html_pages/[^"]+\.html)"[^>]*>\s*<span class="name">(.*?)</span>', re.S)
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
X_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Claude may only edit files and run the site check and tests ...
BASE_TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(.venv/Scripts/python.exe -m tools.site_check:*)",
    "Bash(.venv/Scripts/python.exe -m pytest:*)",
    "Bash(.venv\\Scripts\\python.exe -m tools.site_check:*)",
    "Bash(.venv\\Scripts\\python.exe -m pytest:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
]
# ... and, only when "Update GitHub" is checked, use git to publish.
PUBLISH_TOOLS = ["Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)"]


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
    filename = f"{stem}{name.suffix.lower()}" if stem.startswith(prefix) else f"{prefix}_{stem}{name.suffix.lower()}"
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


def _column_index(ref: str) -> int:
    """Zero-based column number of a cell reference such as 'C7'."""
    letters = re.match(r"[A-Z]+", ref.upper())
    index = 0
    for ch in letters.group(0) if letters else "A":
        index = index * 26 + ord(ch) - 64
    return index - 1


def xlsx_to_text(path: Path) -> str:
    """Return every sheet of an .xlsx as text: a '## Sheet' heading, then 'a | b | c' rows."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).iter(f"{X_NS}si"):
                shared.append("".join(t.text or "" for t in item.iter(f"{X_NS}t")))
        rels = {r.get("Id"): r.get("Target", "")
                for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).iter(f"{PKG_NS}Relationship")}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        blocks: list[str] = []
        for sheet in workbook.iter(f"{X_NS}sheet"):
            target = rels.get(sheet.get(f"{R_NS}id"), "").lstrip("/")
            target = target if target.startswith("xl/") else f"xl/{target}"
            if target not in names:
                continue
            rows: list[str] = []
            for row in ET.fromstring(archive.read(target)).iter(f"{X_NS}row"):
                values: dict[int, str] = {}
                for cell in row.findall(f"{X_NS}c"):
                    kind = cell.get("t", "n")
                    value = cell.find(f"{X_NS}v")
                    if kind == "s" and value is not None:
                        text = shared[int(value.text or 0)]
                    elif kind == "inlineStr":
                        text = "".join(t.text or "" for t in cell.iter(f"{X_NS}t"))
                    elif kind == "b" and value is not None:
                        text = "TRUE" if value.text == "1" else "FALSE"
                    else:
                        text = value.text or "" if value is not None else ""
                    if text.strip():
                        values[_column_index(cell.get("r", "A"))] = text.strip()
                if values:
                    rows.append(" | ".join(values.get(i, "") for i in range(max(values) + 1)))
            if rows:
                blocks.append(f"## Sheet: {sheet.get('name', '')}\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def prepare_material(page: Page, file: Path | None, text: str, root: Path = PROJECT_DIR,
                     instructions: str = "") -> Material:
    """Copy or convert the inputs and describe them for the prompt.

    A job needs a source file, text, or instructions (instructions alone = edits to the page).
    """
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
        elif suffix in EXCEL_TYPES:
            converted = work / f"{safe_name(file.stem)}.txt"
            converted.write_text(xlsx_to_text(file), encoding="utf-8")
            material.lines.append(f"- Source Excel workbook '{file.name}', converted to text in "
                                  f"{converted.relative_to(root).as_posix()} (one block per sheet, cells as 'a | b').")
        else:
            copied = work / file.name
            shutil.copy2(file, copied)
            kind = "PDF" if suffix in PDF_TYPES else "HTML file" if suffix in {".html", ".htm"} else "text file"
            material.lines.append(f"- Source {kind} '{file.name}', copied to {copied.relative_to(root).as_posix()}.")

    if text.strip():
        material.lines.append("- Text typed or pasted by the user, between the markers:\n"
                              "<<<USER TEXT\n" + text.strip() + "\nUSER TEXT>>>")

    if not material.lines and not instructions.strip():
        raise ValueError("Nothing to do: choose a source file, enter text, or enter instructions.")
    return material


def build_prompt(page: Page, material: Material, instructions: str = "", publish: bool = True,
                 today: date | None = None) -> str:
    """The instructions given to Claude for this job."""
    day = (today or date.today()).isoformat()
    images = (f"\n- {len(material.images)} image(s) were copied into kb_images/. Show each one where it belongs, "
              "in the page style, with alt text. If an image is not useful on the page, do not show it, and "
              "say so in your report." if material.images else "")
    if publish:
        finish = ("Fix any problem they report. Then git add only the files you changed (including new kb_images\n"
                  "  files), git commit with a short message, and git push origin main.")
        report = "and whether it was published"
    else:
        finish = ("Fix any problem they report. Do NOT git add, commit, or push: the user asked for a local\n"
                  "  update only (this overrides the CLAUDE.md publishing rule for this job).")
        report = "and that it was updated locally only (not published)"
    user_rules = ("\nUSER INSTRUCTIONS for this job. Carry out every one of them while you do the work above; they\n"
                  "take priority over the defaults above (but not over the git rule just stated). In your report,\n"
                  "say for each instruction what you did, or why it could not be done:\n"
                  f"<<<INSTRUCTIONS\n{instructions.strip()}\nINSTRUCTIONS>>>\n" if instructions.strip() else "")
    task = (f'add the new material below to the page "{page.name}" ({page.path})' if material.lines else
            f'apply the USER INSTRUCTIONS below to the page "{page.name}" ({page.path}); there is no new material')
    return f"""You are updating the JCR Knowledge Bank website in this folder. Follow CLAUDE.md exactly.

TASK: {task}.

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
  {finish}
- If the material does not fit this page at all, or cannot be read, change nothing and explain why.
{user_rules}
Finish with a short plain-text report for the user (no tables): what was added and where, any corrections,
{report}.

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


def allowed_tools(publish: bool) -> list[str]:
    """Tools Claude may use: file edits, checks, and git publishing only when asked."""
    return BASE_TOOLS + (PUBLISH_TOOLS if publish else [])


def claude_args(executable: str, publish: bool = True) -> list[str]:
    """Command line for a non-interactive Claude run (the prompt goes to stdin)."""
    return [executable, "-p", "--output-format", "text", "--permission-mode", "acceptEdits",
            "--allowedTools", *allowed_tools(publish)]


def _no_window() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def git(args: list[str], root: Path = PROJECT_DIR) -> str:
    """Run a git command in the project folder and return its output (raises on failure)."""
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", creationflags=_no_window())
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{(result.stderr or result.stdout).strip()}")
    return result.stdout


def changed_files(root: Path = PROJECT_DIR) -> dict[str, str]:
    """Changed or new files (git status) mapped to a hash of their content ('' if deleted)."""
    out = git(["status", "--porcelain=v1", "-z", "-uall"], root)
    entries = out.split("\0")
    result: dict[str, str] = {}
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if status[0] in "RC":
            i += 1  # the next entry is the original name
        file = root / path
        result[path] = hashlib.sha1(file.read_bytes()).hexdigest() if file.is_file() else ""
    return result


def files_changed_since(before: dict[str, str], root: Path = PROJECT_DIR) -> list[str]:
    """Files that changed after the snapshot 'before' was taken."""
    after = changed_files(root)
    return sorted(path for path, digest in after.items() if before.get(path) != digest)


def publish_files(paths: list[str], message: str, root: Path = PROJECT_DIR) -> str:
    """Commit only these files and push to GitHub. Returns the new commit line."""
    if not paths:
        raise ValueError("No changed files to publish.")
    git(["add", "-A", "--", *paths], root)
    git(["commit", "-m", message, "--", *paths], root)
    git(["push", "origin", "main"], root)
    return git(["log", "--oneline", "-1"], root).strip()


@dataclass
class SyncState:
    """How the local knowledge bank differs from GitHub."""

    files: list[str]  # local changes not committed yet (edited, new, or deleted files)
    unpushed: list[str]  # local commits not on GitHub yet
    behind: int  # GitHub commits not on this computer

    @property
    def matching(self) -> bool:
        return not self.files and not self.unpushed and not self.behind


def github_state(root: Path = PROJECT_DIR, branch: str = "main") -> SyncState:
    """Compare the local knowledge bank with GitHub (fetches first)."""
    git(["fetch", "-q", "origin", branch], root)
    unpushed = [line for line in git(["log", "--oneline", f"origin/{branch}..HEAD"], root).splitlines() if line]
    behind = int(git(["rev-list", "--count", f"HEAD..origin/{branch}"], root).strip() or 0)
    return SyncState(sorted(changed_files(root)), unpushed, behind)


def match_github(root: Path = PROJECT_DIR, branch: str = "main",
                 message: str = "KB: match GitHub with the local knowledge bank") -> str:
    """Make GitHub match the local knowledge bank exactly: commit every local change and push.

    Refuses when GitHub has newer commits, so nothing on GitHub is ever overwritten.
    Returns a one-line summary.
    """
    state = github_state(root, branch)
    if state.behind:
        raise RuntimeError(f"GitHub has {state.behind} newer commit(s) that are not on this computer. "
                           "Nothing was changed. Get those changes first (git pull), then try again.")
    if state.matching:
        return "Already matching: GitHub has everything from the local knowledge bank."
    if state.files:
        git(["add", "-A"], root)
        git(["commit", "-q", "-m", message], root)
    git(["push", "origin", branch], root)
    return "Matched: " + git(["log", "--oneline", "-1"], root).strip()


def run_checks(root: Path = PROJECT_DIR) -> str:
    """Run the site check and tests. Returns '' when all good, else a description of the problems."""
    from tools.site_check import check_site

    problems = [f"Site check: {issue}" for issue in check_site(root)]
    python = root / ".venv" / "Scripts" / "python.exe"
    tests = subprocess.run([str(python if python.exists() else sys.executable), "-m", "pytest", "-q"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=_no_window())
    if tests.returncode != 0:
        problems.append("Tests failed:\n" + "\n".join(tests.stdout.strip().splitlines()[-15:]))
    return "\n".join(problems)


# ---------- Window ----------

class AddDataWindow:
    """The KNOWLEDGE BANK ADD DATA window (Chart Price Plot style, maximized)."""

    def __init__(self, root: tk.Tk, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self.started = 0.0
        self.busy = False
        self.pages: list[Page] = []

        root.title("KNOWLEDGE BANK ADD DATA")
        root.configure(bg=WHITE)
        icon = PROJECT_DIR / "assets" / "knowledge_bank.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
        # Normal window chrome (minimize / maximize / close), maximized on open.
        root.state("zoomed")

        self.page_var = tk.StringVar()
        self.file_var = tk.StringVar()
        self.github_var = tk.BooleanVar(value=True)
        self.match_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Choose a page, then a source file, text, or instructions.")

        self._build_layout()
        root.protocol("WM_DELETE_WINDOW", self.exit)
        root.bind("<Escape>", lambda _e: self.exit())
        root.report_callback_exception = self._callback_error  # type: ignore[assignment]
        self.load_pages()

    # ----- layout -----

    def _build_layout(self) -> None:
        # The input block sits in a scrollable canvas: centered when it fits, top-aligned
        # with a right scrollbar when it does not (same as Chart Price Plot).
        container = tk.Frame(self.root, bg=WHITE)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(container, bg=WHITE, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        v_scroll.grid_remove()
        canvas.configure(yscrollcommand=v_scroll.set)
        self.canvas, self.v_scroll = canvas, v_scroll

        block = tk.Frame(canvas, bg=WHITE)
        block_window = canvas.create_window(0, 0, window=block, anchor="n")
        block.columnconfigure(1, weight=1)

        row = 0
        tk.Label(block, text="KNOWLEDGE BANK ADD DATA", bg=WHITE, fg=TEXT_COLOR, font=TITLE_FONT
                 ).grid(row=row, column=0, columnspan=3, pady=(0, 4))
        row += 1
        tk.Label(block, text="Add a source file, text, or instructions to a JCR Knowledge Bank page", bg=WHITE,
                 fg=GRAY, font=SUBTITLE_FONT).grid(row=row, column=0, columnspan=3, pady=(0, 10))
        row += 1

        self._label(block, "Target page:", row)
        self.page_box = ttk.Combobox(block, textvariable=self.page_var, state="readonly", font=ENTRY_FONT)
        self.page_box.grid(row=row, column=1, sticky="ew", padx=(12, 8), pady=4)
        self.view_btn = tk.Button(block, text="View page...", font=SMALL_FONT, command=self.view_page)
        self.view_btn.grid(row=row, column=2, sticky="w", pady=4)
        row += 1

        self._label(block, "Source file:", row)
        self.file_entry = tk.Entry(block, textvariable=self.file_var, font=ENTRY_FONT)
        self.file_entry.grid(row=row, column=1, sticky="ew", padx=(12, 8), pady=4)
        self.browse_btn = tk.Button(block, text="Browse...", font=SMALL_FONT, command=self.browse)
        self.browse_btn.grid(row=row, column=2, sticky="w", pady=4)
        row += 1

        self._label(block, "Instructions:", row, columnspan=2, pady=(6, 2))
        self.github_check = tk.Checkbutton(block, text="Update GitHub", variable=self.github_var, bg=WHITE,
                                           fg=TEXT_COLOR, font=SMALL_FONT, anchor="w",
                                           activebackground=WHITE)
        self.github_check.grid(row=row, column=2, sticky="w", pady=(6, 2))
        row += 1
        self.instructions = self._text_box(block, row, height=5)
        self.match_check = tk.Checkbutton(block, text="Match GitHub", variable=self.match_var, bg=WHITE,
                                          fg=TEXT_COLOR, font=SMALL_FONT, anchor="w", activebackground=WHITE,
                                          command=self._apply_mode)
        self.match_check.grid(row=row, column=2, sticky="nw")
        row += 1

        self._label(block, "Text:", row, columnspan=2, pady=(6, 2))
        row += 1
        self.text = self._text_box(block, row, height=20)

        # Button column right of the text box (Chart Price Plot style).
        button_col = tk.Frame(block, bg=WHITE)
        button_col.grid(row=row, column=2, sticky="nw", padx=(12, 0))
        self.process_btn = tk.Button(button_col, text="PROCESS", font=BUTTON_FONT, command=self.process_data,
                                     width=8, padx=15, pady=5, fg=TEXT_COLOR)
        self.process_btn.pack(side="top")
        tk.Button(button_col, text="EXIT", font=BUTTON_FONT, command=self.exit, width=8, padx=15, pady=5,
                  fg=TEXT_COLOR).pack(side="top", pady=(16, 0))
        row += 1

        self.status = tk.Label(block, textvariable=self.status_var, bg=WHITE, fg=GREEN, font=STATUS_FONT,
                               anchor="w", justify="left")
        self.status.grid(row=row, column=0, columnspan=3, sticky="w", pady=(6, 0))

        def relayout(_event: Any = None) -> None:
            cw, ch = canvas.winfo_width(), canvas.winfo_height()
            # Text boxes take 80% of the window width; the button column sits to their right.
            width = int(cw * TEXT_WIDTH) + button_col.winfo_reqwidth() + 12
            canvas.itemconfigure(block_window, width=min(width, cw - 20))
            self.status.configure(wraplength=max(300, int(cw * TEXT_WIDTH)))
            bh = block.winfo_reqheight()
            margin = 8
            fits = bh + 2 * margin <= ch
            y = (ch - bh) // 2 if fits else margin
            canvas.coords(block_window, cw // 2, y)
            canvas.configure(scrollregion=(0, 0, cw, max(ch, bh + 2 * margin)))
            if fits:
                v_scroll.grid_remove()
                canvas.yview_moveto(0)
            else:
                v_scroll.grid()

        block.bind("<Configure>", relayout)
        canvas.bind("<Configure>", relayout)
        self.root.bind_all("<MouseWheel>", self._on_mouse_wheel)
        self.root.bind_all("<Control-MouseWheel>", self._on_ctrl_mouse_wheel)
        self._install_zoom_fonts(block)

    def _label(self, parent: tk.Frame, text: str, row: int, columnspan: int = 1,
               pady: tuple[int, int] | int = 6) -> None:
        tk.Label(parent, text=text, bg=WHITE, fg=TEXT_COLOR, font=LABEL_FONT, anchor="w"
                 ).grid(row=row, column=0, columnspan=columnspan, sticky="w", pady=pady)

    def _text_box(self, parent: tk.Frame, row: int, height: int) -> tk.Text:
        frame = tk.Frame(parent, bg=WHITE, relief="sunken", bd=1)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        box = tk.Text(frame, height=height, font=TEXT_FONT, wrap="word", relief="flat", bd=4, undo=True)
        scroll = tk.Scrollbar(frame, command=box.yview)
        box.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        box.pack(side="left", fill="both", expand=True)
        return box

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        # Text boxes scroll themselves; the window scrolls only when taller than the screen.
        if isinstance(event.widget, tk.Text):
            return
        if self.v_scroll.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _install_zoom_fonts(self, widget: tk.Misc) -> None:
        """Share one Font per font spec so Ctrl + mouse wheel can zoom the whole window."""
        self._zoom = 1.0
        self._zoom_fonts: dict[str, tuple[tkfont.Font, int]] = {}

        def walk(w: tk.Misc) -> None:
            try:
                spec = w.cget("font")
            except tk.TclError:
                spec = None
            if spec:
                key = str(spec)
                if key not in self._zoom_fonts:
                    f = tkfont.Font(root=self.root, font=spec)
                    self._zoom_fonts[key] = (f, f.cget("size"))
                try:
                    w.configure(font=self._zoom_fonts[key][0])
                except tk.TclError:
                    pass
            for child in w.winfo_children():
                walk(child)

        walk(widget)

    def _on_ctrl_mouse_wheel(self, event: tk.Event) -> str:
        step = 0.1 if event.delta > 0 else -0.1
        self._zoom = min(2.0, max(0.6, round(self._zoom + step, 1)))
        for f, base in self._zoom_fonts.values():
            sign = -1 if base < 0 else 1
            f.configure(size=sign * max(6, round(abs(base) * self._zoom)))
        return "break"

    def _callback_error(self, exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        log.error("Window callback error", exc_info=(exc_type, exc, tb))
        messagebox.showerror("Error", f"{exc}\n\nDetails are in logs\\app.log", parent=self.root)

    def _set_status(self, text: str, color: str = GREEN) -> None:
        self.status_var.set(text)
        self.status.configure(fg=color)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.process_btn.configure(state="disabled" if busy else "normal")
        self.match_check.configure(state="disabled" if busy else "normal")
        self._apply_mode()

    def _apply_mode(self) -> None:
        """Enable the page inputs, unless busy or Match GitHub is checked (no page work then)."""
        matching = self.match_var.get()
        state = "disabled" if self.busy or matching else "normal"
        for widget in (self.browse_btn, self.file_entry, self.view_btn, self.github_check,
                       self.instructions, self.text):
            widget.configure(state=state)
        self.page_box.configure(state="disabled" if self.busy or matching else "readonly")
        for box in (self.instructions, self.text):
            box.configure(bg="#f0f0f0" if matching else WHITE)
        if not self.busy:
            self._set_status("Match GitHub: PROCESS publishes every local change not yet on GitHub."
                             if matching else "Choose a page, then a source file, text, or instructions.")

    # ----- actions -----

    def load_pages(self) -> None:
        self.pages = list_pages()
        self.page_box["values"] = [p.name for p in self.pages]
        log.info("Add data: %d page(s) listed", len(self.pages))

    def selected_page(self) -> Page | None:
        name = self.page_var.get()
        return next((p for p in self.pages if p.name == name), None)

    def page_url(self, page: Page, live: bool = True) -> str:
        if live:
            return self.config["site_url"].rstrip("/") + "/" + page.path
        return (PROJECT_DIR / page.path).as_uri()

    def view_page(self) -> None:
        page = self.selected_page()
        if page is None:
            self._set_status("Choose a target page first.", RED)
            return
        webbrowser.open(self.page_url(page, live=self.github_var.get()))

    def browse(self) -> None:
        start = PROJECT_DIR / "data"
        kinds = " ".join(f"*{s}" for s in sorted(SUPPORTED_TYPES))
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose the source file",
                                            initialdir=str(start if start.exists() else PROJECT_DIR),
                                            filetypes=[("Supported files", kinds)])
        if chosen:
            self.file_var.set(str(Path(chosen)))

    def process_data(self) -> None:
        if self.match_var.get():
            self.start_match()
            return
        page = self.selected_page()
        file_text = self.file_var.get().strip().strip('"')
        text = self.text.get("1.0", "end").strip()
        instructions = self.instructions.get("1.0", "end").strip()
        publish = self.github_var.get()
        if page is None:
            self._set_status("Choose a target page first.", RED)
            return
        if not file_text and not text and not instructions:
            self._set_status("Choose a source file, enter text, or enter instructions.", RED)
            return
        file = Path(file_text) if file_text else None
        if file is not None:
            if not file.is_file():
                self._set_status(f"File not found: {file}", RED)
                return
            if file.suffix.lower() not in SUPPORTED_TYPES:
                self._set_status(f"Unsupported file type '{file.suffix}'. Use: "
                                 f"{', '.join(sorted(SUPPORTED_TYPES))}", RED)
                return
        log.info("User: PROCESS page=%s file=%s text=%d chars instructions=%d chars github=%s",
                 page.path, file, len(text), len(instructions), publish)
        self._set_busy(True)
        self.started = time.monotonic()
        self._tick(publish)
        threading.Thread(target=self._run_job, args=(page, file, text, instructions, publish),
                         daemon=True, name="add-data").start()

    def _tick(self, publish: bool) -> None:
        if self.started == 0.0:
            return
        elapsed = int(time.monotonic() - self.started)
        where = "checking, and publishing" if publish else "and checking (local only)"
        self._set_status(f"Working... {elapsed // 60}:{elapsed % 60:02d}   Claude is updating the page {where}. "
                         "This usually takes 1 to 5 minutes.", BLUE)
        self.root.after(1000, self._tick, publish)

    def _run_job(self, page: Page, file: Path | None, text: str, instructions: str, publish: bool) -> None:
        try:
            before = changed_files()
            material = prepare_material(page, file, text, instructions=instructions)
            prompt = build_prompt(page, material, instructions, publish)
            args = claude_args(find_claude(), publish)
            timeout = float(self.config.get("add_data_timeout_minutes", 20)) * 60
            log.info("Add data: starting Claude for %s (publish=%s)", page.path, publish)
            self.process = subprocess.Popen(args, cwd=PROJECT_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                            creationflags=_no_window())
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
            changed = [] if publish else files_changed_since(before)
            self._post(self._done, page, out.strip() or "Done.", publish, changed, None)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("Add data failed")
            self.process = None
            self._post(self._done, page, "", publish, [], exc)

    def _post(self, *args: Any) -> None:
        """Run a callback on the window thread, unless the window was closed."""
        try:
            self.root.after(0, *args)
        except (RuntimeError, tk.TclError):
            log.info("Add data: window closed before the job finished")

    def _done(self, page: Page, report: str, publish: bool, changed: list[str], error: Exception | None) -> None:
        self.started = 0.0
        self._set_busy(False)
        if error:
            self._set_status("Not added. See the message for details.", RED)
            messagebox.showerror("Knowledge Bank Add Data", f"{error}\n\nDetails are in logs\\app.log", parent=self.root)
            return
        self.file_var.set("")
        self.text.delete("1.0", "end")
        self.instructions.delete("1.0", "end")
        if publish:
            self._set_status(f"Done: {page.name}. The live page updates in 1 to 2 minutes.")
            ResultWindow(self.root, page, report, self.page_url(page, live=True))
            return
        self._set_status(f"Done: {page.name} updated locally (not on GitHub).")
        result = ResultWindow(self.root, page, report, self.page_url(page, live=False))
        if not changed:
            return
        listing = "\n".join(f"  {p}" for p in changed[:15]) + ("\n  ..." if len(changed) > 15 else "")
        if messagebox.askyesno("Knowledge Bank Add Data", f"The page was updated locally only.\n\nChanged files:\n{listing}\n\n"
                               "Update GitHub now?", parent=result.window):
            self._set_busy(True)
            self._set_status("Publishing to GitHub...", BLUE)
            threading.Thread(target=self._run_publish, args=(page, changed), daemon=True, name="publish").start()

    def _run_publish(self, page: Page, changed: list[str]) -> None:
        try:
            commit = publish_files(changed, f"KNOWLEDGE BANK ADD DATA: {page.name}")
            log.info("Add data: published %s", commit)
            self._post(self._published, page, None)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("Publishing failed")
            self._post(self._published, page, exc)

    def _published(self, page: Page, error: Exception | None) -> None:
        self._set_busy(False)
        if error:
            self._set_status("Not published. See the message for details.", RED)
            messagebox.showerror("Knowledge Bank Add Data", f"{error}\n\nDetails are in logs\\app.log", parent=self.root)
        else:
            self._set_status(f"Published: {page.name}. The live page updates in 1 to 2 minutes.")

    # ----- Match GitHub -----

    def start_match(self) -> None:
        log.info("User: PROCESS with Match GitHub")
        self._set_busy(True)
        self._set_status("Match GitHub: comparing the local knowledge bank with GitHub...", BLUE)
        threading.Thread(target=self._match_scan, daemon=True, name="match-scan").start()

    def _match_scan(self) -> None:
        try:
            self._post(self._match_confirm, github_state(), None)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("Match GitHub: compare failed")
            self._post(self._match_confirm, None, exc)

    def _match_confirm(self, state: SyncState | None, error: Exception | None) -> None:
        if error or state is None:
            self._match_finish(f"Could not compare with GitHub:\n{error}", ok=False)
            return
        if state.behind:
            self._match_finish(f"GitHub has {state.behind} newer commit(s) that are not on this computer.\n"
                               "Nothing was changed, so nothing on GitHub is overwritten.", ok=False)
            return
        if state.matching:
            self._match_finish("Already matching: GitHub has everything from the local knowledge bank.", ok=True)
            return
        lines = [f"  {p}" for p in state.files[:20]] + (["  ..."] if len(state.files) > 20 else [])
        parts = []
        if state.files:
            parts.append(f"{len(state.files)} local file change(s) not on GitHub:\n" + "\n".join(lines))
        if state.unpushed:
            parts.append(f"{len(state.unpushed)} local commit(s) not on GitHub:\n"
                         + "\n".join(f"  {c}" for c in state.unpushed[:10]))
        question = "\n\n".join(parts) + "\n\nRun the site check and tests, then publish all of this to GitHub?"
        if not messagebox.askyesno("Match GitHub", question, parent=self.root):
            self._match_finish("Match GitHub canceled. Nothing was changed.", ok=True, popup=False)
            return
        self._set_status("Match GitHub: checking the site and running tests, then publishing...", BLUE)
        threading.Thread(target=self._match_run, daemon=True, name="match-run").start()

    def _match_run(self) -> None:
        try:
            problems = run_checks()
            if problems:
                self._post(self._match_finish, "Not published. Fix these problems first:\n\n" + problems, False)
                return
            summary = match_github()
            log.info("Match GitHub: %s", summary)
            self._post(self._match_finish, summary + "\nThe live site updates in 1 to 2 minutes.", True)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            log.exception("Match GitHub failed")
            self._post(self._match_finish, f"Match GitHub failed:\n{exc}", False)

    def _match_finish(self, message: str, ok: bool, popup: bool = True) -> None:
        self._set_busy(False)
        self._set_status(message.splitlines()[0], GREEN if ok else RED)
        if popup:
            (messagebox.showinfo if ok else messagebox.showerror)("Match GitHub", message, parent=self.root)

    def exit(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno("Knowledge Bank Add Data", "A job is still running. Stop it and exit?", parent=self.root):
                return
            log.info("User: EXIT, stopping the running job")
            self.process.kill()
        log.info("User: EXIT")
        self.root.destroy()


class ResultWindow:
    """Shows Claude's report after a job."""

    def __init__(self, parent: tk.Tk, page: Page, report: str, url: str) -> None:
        win = tk.Toplevel(parent, bg=WHITE)
        self.window = win
        win.title("Knowledge Bank Add Data - Result")
        win.geometry(f"760x500+{parent.winfo_rootx() + 120}+{parent.winfo_rooty() + 80}")
        icon = PROJECT_DIR / "assets" / "knowledge_bank.ico"
        if icon.exists():
            win.iconbitmap(str(icon))
        tk.Label(win, text=f"Result: {page.name}", font=("Segoe UI", 16, "bold"), bg=WHITE, fg=TEXT_COLOR,
                 anchor="w").pack(fill="x", padx=24, pady=(18, 10))
        frame = tk.Frame(win, bg=WHITE, relief="sunken", bd=1)
        frame.pack(fill="both", expand=True, padx=24)
        text = tk.Text(frame, font=TEXT_FONT, wrap="word", relief="flat", bd=6)
        scroll = tk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.insert("1.0", report)
        text.configure(state="disabled")
        buttons = tk.Frame(win, bg=WHITE)
        buttons.pack(pady=14)
        for label, command in (("VIEW PAGE", lambda: webbrowser.open(url)), ("CLOSE", win.destroy)):
            tk.Button(buttons, text=label, command=command, font=BUTTON_FONT, width=10, padx=15, pady=5,
                      fg=TEXT_COLOR).pack(side="left", padx=8)
        win.bind("<Escape>", lambda _e: win.destroy())


def run(config: dict[str, Any]) -> None:
    """Open the KNOWLEDGE BANK ADD DATA window."""
    root = tk.Tk()
    AddDataWindow(root, config)
    root.mainloop()


if __name__ == "__main__":
    from tools.kb_core import start

    os.chdir(PROJECT_DIR)
    run(start(show_dialog=True))

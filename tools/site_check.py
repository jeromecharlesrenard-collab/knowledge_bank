"""Check the website for problems that would show up on GitHub Pages.

Checks:
- every local link and image exists, with the exact upper/lowercase spelling
  (Windows ignores case, GitHub Pages does not)
- every knowledge page has a <title>, the shared stylesheet, and the return arrow
- every knowledge page is listed on the home page (index.html), with no duplicates

Usage:  .venv\\Scripts\\python.exe -m tools.site_check
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools.kb_core import PROJECT_DIR, log, start

SKIP_DIRS = {
    ".git", ".venv", ".vscode", ".pytest_cache", "__pycache__",
    "data", "docs", "logs", "templates", "tests", "tools",
}
EXTERNAL_PREFIXES = ("http:", "https:", "mailto:", "tel:", "data:", "javascript:", "#", "//")
STYLESHEET = "assets/kb_style.css"


@dataclass(frozen=True)
class Issue:
    """One problem found on a page."""

    page: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.page}: {self.detail}"


@dataclass
class PageInfo:
    """Links and markers collected from one HTML page."""

    refs: list[str] = field(default_factory=list)
    title: str = ""
    has_return_arrow: bool = False
    has_stylesheet: bool = False
    entries: list[tuple[str, str]] = field(default_factory=list)  # (name, href) on the home page


class _PageParser(HTMLParser):
    """Collect href/src values, the title, and Knowledge Bank markers."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.info = PageInfo()
        self._in_title = False
        self._in_entry = False
        self._entry_href = ""
        self._in_name = False
        self._name = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        for key in ("href", "src"):
            if a.get(key):
                self.info.refs.append(a[key])
        classes = a.get("class", "").split()
        if tag == "title":
            self._in_title = True
        elif tag == "a" and "return-arrow" in classes and a.get("href") == "index.html":
            self.info.has_return_arrow = True
        elif tag == "link" and a.get("rel") == "stylesheet" and a.get("href") == STYLESHEET:
            self.info.has_stylesheet = True
        elif tag == "li" and "entry" in classes:
            self._in_entry, self._entry_href, self._name = True, "", ""
        elif tag == "a" and self._in_entry:
            self._entry_href = a.get("href", "")
        elif tag == "span" and "name" in classes and self._in_entry:
            self._in_name = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "span" and self._in_name:
            self._in_name = False
        elif tag == "li" and self._in_entry:
            self._in_entry = False
            self.info.entries.append((self._name.strip(), self._entry_href))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.info.title += data
        if self._in_name:
            self._name += data


def parse_page(path: Path) -> PageInfo:
    """Parse one HTML file."""
    parser = _PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.info


def site_pages(root: Path = PROJECT_DIR) -> list[Path]:
    """All published HTML pages (development folders are skipped)."""
    pages: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        pages += [Path(dirpath) / f for f in sorted(filenames) if f.lower().endswith(".html")]
    return pages


def is_local(ref: str) -> bool:
    """True for links to files inside the site."""
    return bool(ref) and not ref.lower().startswith(EXTERNAL_PREFIXES)


def resolve_exact(root: Path, target: Path) -> str:
    """Return 'ok', 'missing', or 'case' (exists only with different upper/lowercase)."""
    # os.path.abspath, not Path.resolve: on Windows resolve() can silently fix the case.
    base = Path(os.path.abspath(root))
    try:
        rel = Path(os.path.abspath(target)).relative_to(base)
    except ValueError:
        return "missing"
    current = base
    for part in rel.parts:
        try:
            names = os.listdir(current)
        except OSError:
            return "missing"
        if part in names:
            current = current / part
        elif part.lower() in (n.lower() for n in names):
            return "case"
        else:
            return "missing"
    return "ok"


def check_site(root: Path = PROJECT_DIR) -> list[Issue]:
    """Run every check and return the list of problems (empty = all good)."""
    issues: list[Issue] = []
    pages = site_pages(root)
    index_path = root / "index.html"
    parsed = {p: parse_page(p) for p in pages}

    for page, info in parsed.items():
        name = page.relative_to(root).as_posix()
        for ref in info.refs:
            if not is_local(ref):
                continue
            path_part = unquote(urlsplit(ref).path)
            if not path_part:
                continue
            target = (page.parent / path_part)
            if path_part.endswith("/"):
                target = target / "index.html"
            status = resolve_exact(root, target)
            if status == "missing":
                issues.append(Issue(name, "missing", f"'{ref}' does not exist"))
            elif status == "case":
                issues.append(Issue(name, "case", f"'{ref}' differs in upper/lowercase from the actual file"))
        if not info.title.strip():
            issues.append(Issue(name, "title", "page has no <title>"))
        if not info.has_stylesheet:
            issues.append(Issue(name, "style", f"page does not link {STYLESHEET}"))
        if page != index_path and not info.has_return_arrow:
            issues.append(Issue(name, "arrow", "page has no return arrow to index.html"))

    if index_path not in parsed:
        issues.append(Issue("index.html", "missing", "home page index.html not found"))
        return issues

    entries = parsed[index_path].entries
    listed = [href for _, href in entries]
    for page in pages:
        if page == index_path:
            continue
        rel = page.relative_to(root).as_posix()
        if rel not in listed:
            issues.append(Issue("index.html", "unlisted", f"'{rel}' is not listed on the home page"))
    names = [n.lower() for n, _ in entries]
    for n in sorted({n for n in names if names.count(n) > 1}):
        issues.append(Issue("index.html", "duplicate", f"entry name '{n}' is listed more than once"))
    return issues


def main() -> int:
    """Run the checks, print a report, and return an exit code (0 = OK)."""
    start()
    log.info("Site check started")
    issues = check_site()
    if issues:
        print(f"{len(issues)} problem(s) found:")
        for issue in issues:
            print(f"  {issue}")
            log.warning("Site check: %s", issue)
    else:
        print(f"All good: {len(site_pages())} page(s) checked, no problems found.")
    log.info("Site check finished with %d problem(s)", len(issues))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())

"""Create a new knowledge page from the template and list it on the home page.

Usage:
  .venv\\Scripts\\python.exe -m tools.new_page --title "Bitcoin" --description "What Bitcoin is and how it works"
  .venv\\Scripts\\python.exe -m tools.new_page          (asks for the title and description)

Options:
  --file NAME.html   file name to use (default: the title, e.g. "Bitcoin.html")
  --source TEXT      source shown in the page footer (default: config.json default_source)
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import date
from pathlib import Path

from tools.kb_core import PROJECT_DIR, log, start

TEMPLATE = Path("templates") / "page_template.html"
INVALID_CHARS = set('\\/:*?"<>|')
ENTRIES_LIST = re.compile(r'(<ul[^>]*id="entries"[^>]*>)(.*?)(\n\s*</ul>)', re.S)

ENTRY_BLOCK = """
      <li class="entry">
        <a href="{href}" title="{desc}">
          <span class="name">{name}</span>
          <span class="desc">{desc}</span>
          <span class="date">Added {added}</span>
        </a>
      </li>"""


def default_filename(title: str) -> str:
    """Turn a title into a file name, keeping its upper/lowercase ("Tesla Cars" -> "Tesla_Cars.html")."""
    stem = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
    if not stem:
        raise ValueError("The title must contain at least one letter or digit")
    return f"{stem}.html"


def validate_filename(filename: str) -> str:
    """Check a page file name and add .html if needed."""
    filename = filename.strip()
    if not filename.lower().endswith(".html"):
        filename += ".html"
    if any(c in INVALID_CHARS for c in filename) or " " in filename:
        raise ValueError(f"Invalid file name '{filename}': no spaces or \\ / : * ? \" < > |")
    if filename.lower() == "index.html":
        raise ValueError("index.html is the home page and cannot be used")
    return filename


def add_index_entry(root: Path, name: str, desc: str, href: str, added: str) -> None:
    """Add a card for the page to the list on index.html (the page sorts it alphabetically)."""
    index = root / "index.html"
    text = index.read_text(encoding="utf-8")
    match = ENTRIES_LIST.search(text)
    if not match:
        raise RuntimeError('index.html has no <ul id="entries"> list')
    if f'href="{href}"' in match.group(2):
        log.info("%s is already listed on index.html", href)
        return
    block = ENTRY_BLOCK.format(
        href=html.escape(href), name=html.escape(name), desc=html.escape(desc), added=added
    )
    text = text[: match.end(2)] + block + text[match.end(2):]
    index.write_text(text, encoding="utf-8", newline="\n")
    log.info("Added %s to index.html", href)


def create_page(
    title: str,
    description: str,
    filename: str | None = None,
    source: str = "JCR research",
    root: Path = PROJECT_DIR,
    today: date | None = None,
) -> Path:
    """Create the page file from the template, add it to index.html, and return its path."""
    title, description = title.strip(), description.strip()
    if not title:
        raise ValueError("A title is required")
    filename = validate_filename(filename or default_filename(title))
    target = root / filename
    existing = {p.name.lower() for p in root.glob("*.html")}
    if filename.lower() in existing:
        raise FileExistsError(f"{filename} already exists")

    added = (today or date.today()).isoformat()
    page = (root / TEMPLATE).read_text(encoding="utf-8")
    for key, value in {
        "TITLE": title, "DESCRIPTION": description, "SOURCE": source, "DATE": added,
    }.items():
        page = page.replace("{{" + key + "}}", html.escape(value))
    target.write_text(page, encoding="utf-8", newline="\n")
    log.info("Created %s", target)

    add_index_entry(root, title, description, filename, added)
    return target


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    config = start()
    parser = argparse.ArgumentParser(description="Create a new JCR Knowledge Bank page.")
    parser.add_argument("--title", help="page title, also the name shown on the home page")
    parser.add_argument("--description", help="one-line description for the home page")
    parser.add_argument("--file", help="file name (default: from the title)")
    parser.add_argument("--source", default=config["default_source"], help="source shown in the footer")
    args = parser.parse_args(argv)

    title = args.title or input("Page title: ")
    description = args.description if args.description is not None else input("One-line description: ")
    try:
        path = create_page(title, description, args.file, args.source)
    except (ValueError, FileExistsError, RuntimeError) as exc:
        log.error("New page not created: %s", exc)
        print(f"Not created: {exc}")
        return 1
    print(f"Created {path.name} and added it to the home page (index.html).")
    print("Next: edit the page content, then run the site check and preview.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

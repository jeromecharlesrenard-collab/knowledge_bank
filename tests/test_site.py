"""Checks on the real website files."""

from __future__ import annotations

from tools.kb_core import PROJECT_DIR
from tools.site_check import check_site, parse_page, site_pages


def test_site_has_no_problems() -> None:
    issues = check_site(PROJECT_DIR)
    assert not issues, "\n".join(str(i) for i in issues)


def test_home_page_lists_tesla() -> None:
    entries = parse_page(PROJECT_DIR / "index.html").entries
    assert ("Tesla", "html_pages/Tesla.html") in entries


def test_development_folders_are_not_pages() -> None:
    names = {p.relative_to(PROJECT_DIR).parts[0] for p in site_pages(PROJECT_DIR)}
    assert not names & {"templates", "tests", "tools", ".venv"}

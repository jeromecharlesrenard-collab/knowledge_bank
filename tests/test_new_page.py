"""Logic tests for tools.new_page on a throwaway site."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools.new_page import create_page, default_filename, validate_filename
from tools.site_check import check_site, parse_page


def test_default_filename_keeps_case() -> None:
    assert default_filename("Tesla Cars & Trucks") == "Tesla_Cars_Trucks.html"


@pytest.mark.parametrize("bad", ["my page.html", "a:b", "index.html", "x?.html"])
def test_invalid_filenames_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_filename(bad)


def test_validate_adds_extension() -> None:
    assert validate_filename("Bitcoin") == "Bitcoin.html"


def test_create_page_and_index_entry(mini_site: Path) -> None:
    path = create_page("Bitcoin", "What Bitcoin is", root=mini_site, today=date(2026, 10, 16))
    assert path == mini_site / "html_pages" / "Bitcoin.html"
    text = path.read_text(encoding="utf-8")
    assert "<title>Bitcoin</title>" in text and "{{" not in text
    assert ("Bitcoin", "html_pages/Bitcoin.html") in parse_page(mini_site / "index.html").entries
    assert check_site(mini_site) == []


def test_special_characters_are_escaped(mini_site: Path) -> None:
    path = create_page("S&P 500", "Index <basics>", root=mini_site)
    assert "S&amp;P 500" in path.read_text(encoding="utf-8")
    assert "Index &lt;basics&gt;" in (mini_site / "index.html").read_text(encoding="utf-8")


def test_existing_page_is_not_overwritten(mini_site: Path) -> None:
    with pytest.raises(FileExistsError):
        create_page("alpha", "Same name, different case", root=mini_site)

"""Logic tests for tools.site_check on a throwaway site."""

from __future__ import annotations

from pathlib import Path

from conftest import PAGE
from tools.site_check import check_site, is_local, resolve_exact


def kinds(root: Path) -> list[str]:
    return sorted(i.kind for i in check_site(root))


def test_valid_site_passes(mini_site: Path) -> None:
    assert check_site(mini_site) == []


def test_wrong_case_image_is_reported(mini_site: Path) -> None:
    (mini_site / "Alpha.html").write_text(
        PAGE.format(title="Alpha", extra='<img src="Assets/return_arrow.svg">'), encoding="utf-8"
    )
    assert kinds(mini_site) == ["case"]


def test_missing_image_is_reported(mini_site: Path) -> None:
    (mini_site / "Alpha.html").write_text(
        PAGE.format(title="Alpha", extra='<img src="images/none.png">'), encoding="utf-8"
    )
    assert kinds(mini_site) == ["missing"]


def test_unlisted_page_is_reported(mini_site: Path) -> None:
    (mini_site / "Beta.html").write_text(PAGE.format(title="Beta", extra=""), encoding="utf-8")
    assert kinds(mini_site) == ["unlisted"]


def test_page_without_arrow_title_or_style(mini_site: Path) -> None:
    (mini_site / "Alpha.html").write_text("<html><body>Bare</body></html>", encoding="utf-8")
    assert kinds(mini_site) == ["arrow", "style", "title"]


def test_external_links_are_ignored() -> None:
    assert not is_local("https://example.com/x.png")
    assert not is_local("#section")
    assert is_local("kb_images/tesla_model_s.png")


def test_resolve_exact(mini_site: Path) -> None:
    assert resolve_exact(mini_site, mini_site / "Alpha.html") == "ok"
    assert resolve_exact(mini_site, mini_site / "alpha.html") == "case"
    assert resolve_exact(mini_site, mini_site / "nothing.html") == "missing"

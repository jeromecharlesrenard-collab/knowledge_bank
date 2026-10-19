"""Shared fixtures: a small throwaway copy of the site for logic tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.kb_core import PROJECT_DIR

INDEX = """<!DOCTYPE html>
<html lang="en"><head><title>JCR Knowledge Bank</title>
<link rel="stylesheet" href="assets/kb_style.css"></head>
<body class="home"><main id="index">
    <ul class="list" id="entries">
      <li class="entry">
        <a href="html_pages/Alpha.html">
          <span class="name">Alpha</span>
          <span class="desc">First page</span>
          <span class="date">Added 2026-10-16</span>
        </a>
      </li>
    </ul>
</main></body></html>
"""

PAGE = """<!DOCTYPE html>
<html lang="en"><head><title>{title}</title>
<link rel="stylesheet" href="../assets/kb_style.css"></head>
<body><a class="return-arrow" href="../index.html"><img src="../assets/return_arrow.svg" alt=""></a>
<h1>{title}</h1>{extra}</body></html>
"""


@pytest.fixture
def mini_site(tmp_path: Path) -> Path:
    """A minimal valid site: index.html, html_pages/Alpha.html, assets, and the real template."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "kb_style.css").write_text("body{}", encoding="utf-8")
    (tmp_path / "assets" / "return_arrow.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "assets" / "kb_common.js").write_text("", encoding="utf-8")
    (tmp_path / "assets" / "knowledge_bank.png").write_bytes(b"")
    (tmp_path / "kb_config.js").write_text("", encoding="utf-8")
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "html_pages").mkdir()
    (tmp_path / "html_pages" / "Alpha.html").write_text(PAGE.format(title="Alpha", extra=""), encoding="utf-8")
    (tmp_path / "templates").mkdir()
    shutil.copy(PROJECT_DIR / "templates" / "page_template.html", tmp_path / "templates")
    return tmp_path

"""Logic tests for tools.add_data (no window, no Claude run)."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from tools.add_data import (
    ALLOWED_TOOLS,
    Page,
    build_prompt,
    claude_args,
    docx_to_text,
    list_pages,
    prepare_material,
    safe_name,
)

ALPHA = Page("Alpha", "html_pages/Alpha.html")

DOCX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Title</w:t></w:r><w:r><w:t>Body text.</w:t></w:r></w:p>
<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>A bullet</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>a</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>b</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>"""


def make_docx(path: Path, with_picture: bool = False) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", DOCX_XML)
        if with_picture:
            archive.writestr("word/media/image1.png", b"png-bytes")
    return path


def test_list_pages_reads_home_page(mini_site: Path) -> None:
    assert list_pages(mini_site) == [ALPHA]


def test_safe_name() -> None:
    assert safe_name("My Photo (1)") == "my_photo_1"
    assert safe_name("***") == "image"


def test_docx_to_text_keeps_bold_bullets_and_tables(tmp_path: Path) -> None:
    text, media = docx_to_text(make_docx(tmp_path / "x.docx"))
    assert text.splitlines()[:3] == ["**Title** Body text.", "- A bullet", "a | b"]
    assert media == []


def test_image_is_copied_to_kb_images_with_page_prefix(mini_site: Path, tmp_path: Path) -> None:
    source = tmp_path / "Model S.JPG"
    source.write_bytes(b"jpg")
    material = prepare_material(ALPHA, source, "", root=mini_site)
    assert [p.name for p in material.images] == ["alpha_model_s.jpg"]
    assert (mini_site / "kb_images" / "alpha_model_s.jpg").read_bytes() == b"jpg"
    # A second copy does not overwrite the first.
    again = prepare_material(ALPHA, source, "", root=mini_site)
    assert again.images[0].name == "alpha_model_s_2.jpg"


def test_docx_is_converted_and_pictures_extracted(mini_site: Path, tmp_path: Path) -> None:
    material = prepare_material(ALPHA, make_docx(tmp_path / "Notes.docx", with_picture=True), "", root=mini_site)
    assert (mini_site / "logs" / "add_data" / "notes.txt").read_text(encoding="utf-8").startswith("**Title**")
    assert [p.name for p in material.images] == ["alpha_notes_image1.png"]


def test_text_only_goes_into_the_prompt(mini_site: Path) -> None:
    material = prepare_material(ALPHA, None, "Moon 384,400 km", root=mini_site)
    prompt = build_prompt(ALPHA, material, today=date(2026, 10, 24))
    assert "Moon 384,400 km" in prompt
    assert "html_pages/Alpha.html" in prompt
    assert "updated 2026-10-24" in prompt


def test_nothing_to_add_or_unsupported_type(mini_site: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        prepare_material(ALPHA, None, "   ", root=mini_site)
    bad = tmp_path / "sheet.xlsx"
    bad.write_bytes(b"")
    with pytest.raises(ValueError):
        prepare_material(ALPHA, bad, "", root=mini_site)


def test_claude_is_limited_to_edits_checks_and_git() -> None:
    args = claude_args("claude")
    assert args[:2] == ["claude", "-p"]
    assert args[-len(ALLOWED_TOOLS):] == ALLOWED_TOOLS
    assert "Bash" not in ALLOWED_TOOLS  # no unrestricted shell

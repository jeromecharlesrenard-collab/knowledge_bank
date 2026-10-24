"""Logic tests for tools.add_data (no window, no Claude run)."""

from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from tools.add_data import (
    PUBLISH_TOOLS,
    Page,
    build_prompt,
    changed_files,
    claude_args,
    docx_to_text,
    files_changed_since,
    git,
    list_pages,
    prepare_material,
    safe_name,
    xlsx_to_text,
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


def make_xlsx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml",
                         '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                         '<sheets><sheet name="Planets" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels",
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/sharedStrings.xml",
                         '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                         '<si><t>Planet</t></si><si><t>Moons</t></si><si><t>Mars</t></si></sst>')
        archive.writestr("xl/worksheets/sheet1.xml",
                         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                         '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                         '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="C2"><v>2</v></c></row>'
                         '</sheetData></worksheet>')
    return path


def test_xlsx_to_text(tmp_path: Path) -> None:
    assert xlsx_to_text(make_xlsx(tmp_path / "x.xlsx")) == "## Sheet: Planets\nPlanet | Moons\nMars |  | 2"


def test_xlsx_is_converted_for_claude(mini_site: Path, tmp_path: Path) -> None:
    material = prepare_material(ALPHA, make_xlsx(tmp_path / "Planets.xlsx"), "", root=mini_site)
    assert "Excel workbook" in material.lines[0]
    assert (mini_site / "logs" / "add_data" / "planets.txt").read_text(encoding="utf-8").startswith("## Sheet")


def test_text_only_goes_into_the_prompt(mini_site: Path) -> None:
    material = prepare_material(ALPHA, None, "Moon 384,400 km", root=mini_site)
    prompt = build_prompt(ALPHA, material, "Put it in the Moon line", today=date(2026, 10, 24))
    assert "Moon 384,400 km" in prompt
    assert "html_pages/Alpha.html" in prompt
    assert "updated 2026-10-24" in prompt
    assert "Put it in the Moon line" in prompt
    assert "git push origin main" in prompt


def test_local_only_prompt_forbids_publishing(mini_site: Path) -> None:
    material = prepare_material(ALPHA, None, "x", root=mini_site)
    prompt = build_prompt(ALPHA, material, publish=False)
    assert "Do NOT git add, commit, or push" in prompt
    assert "USER INSTRUCTIONS" not in prompt  # no instructions given


def test_nothing_to_add_or_unsupported_type(mini_site: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        prepare_material(ALPHA, None, "   ", root=mini_site)
    bad = tmp_path / "notes.pdf"
    bad.write_bytes(b"")
    with pytest.raises(ValueError):
        prepare_material(ALPHA, bad, "", root=mini_site)


def test_claude_tools_depend_on_update_github() -> None:
    publish = claude_args("claude", publish=True)
    local = claude_args("claude", publish=False)
    assert publish[:2] == ["claude", "-p"]
    assert all(t in publish for t in PUBLISH_TOOLS)
    assert not any(t in local for t in PUBLISH_TOOLS)
    assert "Bash" not in publish  # never an unrestricted shell


def test_only_files_changed_by_the_job_are_found(tmp_path: Path) -> None:
    git(["init", "-q"], tmp_path)
    (tmp_path / "old.txt").write_text("a", encoding="utf-8")
    (tmp_path / "page.html").write_text("v1", encoding="utf-8")
    git(["add", "."], tmp_path)
    git(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"], tmp_path)
    (tmp_path / "old.txt").write_text("edited before the job", encoding="utf-8")
    before = changed_files(tmp_path)
    # The job edits the page, adds an image, and leaves old.txt alone.
    (tmp_path / "page.html").write_text("v2", encoding="utf-8")
    (tmp_path / "kb_images").mkdir()
    (tmp_path / "kb_images" / "page_x.png").write_bytes(b"png")
    assert files_changed_since(before, tmp_path) == ["kb_images/page_x.png", "page.html"]

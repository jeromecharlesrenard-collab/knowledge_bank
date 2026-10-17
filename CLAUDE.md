# JCR Knowledge Bank

## Purpose
Static website of knowledge pages, published with GitHub Pages:
- Live site: https://jeromecharlesrenard-collab.github.io/knowledge_bank/
- Repo: https://github.com/jeromecharlesrenard-collab/knowledge_bank (branch `main`, remote `origin`)

`index.html` is the home page ("JCR KNOWLEDGE BANK") with an alphabetical list of pages. Each knowledge page (e.g. `Tesla.html`) sits in the project root.

## Folder Structure
```
knowledge_bank/
├── index.html               home page (alphabetical list; sorted/grouped by assets/kb_common.js)
├── Tesla.html               knowledge page
├── Tesla_images/            images for Tesla.html (one <Page>_images/ folder per page)
├── kb_config.js             page settings: return arrow size (%), top/left margins (pt)
├── assets/
│   ├── kb_style.css         shared stylesheet - ALL page styling lives here
│   ├── kb_common.js         applies kb_config.js, sorts the home page list
│   ├── return_arrow.svg     top-left return icon
│   └── knowledge_bank.ico   icon for the shortcut / preview window
├── templates/page_template.html   starting point for new pages
├── main.py                  entry point: logging + config + local preview window
├── tools/                   kb_core.py (paths, config, logging), new_page.py, site_check.py, preview.py
├── tests/                   pytest tests (logic only, no GUI)
├── docs/knowledge_bank NOTES.md
├── data/                    private source documents (git-ignored, never published)
├── logs/app.log             rotating log (git-ignored)
├── config.json              tool settings: log_level, preview_port, site_url, repo_url, default_source
├── requirements.txt         pinned dev dependencies
├── pytest.ini, .editorconfig, .gitignore, .gitattributes, .nojekyll
└── .vscode/                 settings, recommended extensions, tasks
```

## Environment
- venv: `C:\Users\Jerome\PYTHON_PROJECTS\knowledge_bank\.venv` (Python 3.14 from `C:\Users\Jerome\AppData\Local\Programs\Python\Python314\python.exe`)
- Dependencies (requirements.txt, pinned): pytest, pillow (icon generation). The website itself needs no Python.

## Commands (run from the project folder)
- Preview site (GitHub-like local server + control window): `.venv\Scripts\pythonw.exe main.py` or the `knowledge_bank.lnk` shortcut
- New page: `.venv\Scripts\python.exe -m tools.new_page --title "Name" --description "One line"`
- Check site (links, images, upper/lowercase, arrow, listing): `.venv\Scripts\python.exe -m tools.site_check`
- Tests: `.venv\Scripts\python.exe -m pytest`
- VS Code: Terminal > Run Task > "KB: Preview site" / "KB: New page" / "KB: Check site" / "KB: Run tests"
- Publish: commit and push to `origin main` (VS Code Source Control); GitHub Pages updates in 1-2 minutes

## Conventions
- **Every page uses the Tesla page style**: link `assets/kb_style.css`, `kb_config.js`, `assets/kb_common.js` in `<head>`; return arrow `<a class="return-arrow" href="index.html">` right after `<body>`. Do not put `<style>` blocks in pages; add shared classes to kb_style.css.
- White background, black Arial text, bold where needed; cards, stat boxes, striped tables (see Tesla.html).
- **No round numbering badges** on cards or boxes (user rule, 2026-10-16).
- Long lists of items: full-width row cards (`.rows` / `.row-card`, see Civilizations_Empires.html): one header line, max 2 text lines, extra details in `<div class="more">` behind the expand icon.
- Home page entries: name on top, description + "Added" date on one single line (CSS cuts long text; full text on hover).
- Create new pages with `tools/new_page.py` (adds the home page entry automatically).
- Page images go in `<Page>_images/` next to the page; file and folder names are case-sensitive on GitHub.
- Run the site check before publishing.
- American spelling. Python: PEP 8, type hints, docstrings, pathlib, paths resolved from the project folder; tools must work under pythonw.exe (no print dependency in GUI code).
- After every change, run the site check and tests, then commit and push to `origin main` without asking (user rule, 2026-10-17). Ask only when there is an open question or a check/test fails. Do not start the preview window without the user's authorization.

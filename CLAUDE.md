# JCR Knowledge Bank

## Purpose
Static website of knowledge pages, published with GitHub Pages:
- Live site: https://jeromecharlesrenard-collab.github.io/knowledge_bank/
- Repo: https://github.com/jeromecharlesrenard-collab/knowledge_bank (branch `main`, remote `origin`)

`index.html` is the home page ("JCR KNOWLEDGE BANK") with an alphabetical list of pages. Every other page sits in `html_pages/` (e.g. `html_pages/Tesla.html`) and reaches shared files with `../` (see Conventions).

## Folder Structure
```
knowledge_bank/
├── index.html               home page (alphabetical list; sorted/grouped by assets/kb_common.js)
├── html_pages/              ALL pages except index.html (e.g. Tesla.html); links use ../
├── kb_images/               ALL page images (kb = knowledge_bank), named <page>_<item>.png
├── kb_config.js             page settings: return arrow size (%), top/left margins (pt)
├── assets/
│   ├── kb_style.css         shared stylesheet - ALL page styling lives here
│   ├── kb_common.js         applies kb_config.js, sorts the home page list
│   ├── return_arrow.svg     top-left return icon
│   └── knowledge_bank.ico   "KB" icon (shortcuts, preview window)
├── templates/page_template.html   starting point for new pages
├── main.py                  entry point: logging + config + local preview window
├── tools/                   kb_core.py (paths, config, logging), new_page.py, site_check.py, preview.py, add_data.py
├── tests/                   pytest tests (logic only, no GUI)
├── docs/knowledge_bank NOTES.md
├── data/                    private source documents (git-ignored, never published)
├── logs/app.log             rotating log (git-ignored)
├── config.json              tool settings: log_level, preview_port, preview_idle_minutes, add_data_timeout_minutes, site_url, repo_url, default_source
├── requirements.txt         pinned dev dependencies
├── pytest.ini, .editorconfig, .gitignore, .gitattributes, .nojekyll
└── .vscode/                 settings, recommended extensions, tasks
```

## Environment
- venv: `C:\Users\Jerome\PYTHON_PROJECTS\knowledge_bank\.venv` (Python 3.14 from `C:\Users\Jerome\AppData\Local\Programs\Python\Python314\python.exe`)
- Dependencies (requirements.txt, pinned): pytest, pillow (icon generation). The website itself needs no Python.

## Commands (run from the project folder)
- Shortcuts (in the project folder and in `PYTHON_PROJECTS\1 PYTHON APPS SHORTCUP`; git-ignored, *.lnk):
  - `KNOWLEDGE BANK L.lnk`: open the site locally, no window (GitHub-like server; it stops by itself after `preview_idle_minutes` in config.json, default 60, without page requests; launching again while it runs just reopens the browser). Same as `.venv\Scripts\pythonw.exe main.py`.
  - `KNOWLEDGE BANK W.lnk`: open the live website.
  - `KNOWLEDGE BANK PREVIEW.lnk`: control window (OPEN SITE / CHECK SITE / EXIT), same as `main.py --window` or VS Code task "KB: Preview window".
  - `ADD KB DATA.lnk`: ADD DATA window (`tools/add_data.py`, same as `main.py --add-data` or task "KB: Add data"). Pick a target page, a source file (.docx, .pdf, text, image) and/or pasted text, then PROCESS. The app copies images (and Word pictures) into kb_images/, converts .docx to text in logs/add_data/, then runs `claude -p` in the project folder (restricted to file edits, site check, tests, git) to place the data in the page style, check, commit, and push. Report shown in a RESULT window and logged in logs/app.log. Timeout: `add_data_timeout_minutes` in config.json.
- New page: `.venv\Scripts\python.exe -m tools.new_page --title "Name" --description "One line"`
- Check site (links, images, upper/lowercase, arrow, listing): `.venv\Scripts\python.exe -m tools.site_check`
- Tests: `.venv\Scripts\python.exe -m pytest`
- VS Code: Terminal > Run Task > "KB: Preview site" / "KB: Preview window" / "KB: Add data" / "KB: New page" / "KB: Check site" / "KB: Run tests"
- Publish: commit and push to `origin main` (VS Code Source Control); GitHub Pages updates in 1-2 minutes

## Conventions
- **Every page uses the Tesla page style**: pages live in `html_pages/` and link `../assets/kb_style.css`, `../kb_config.js`, `../assets/kb_common.js` in `<head>`; return arrow `<a class="return-arrow" href="../index.html">` right after `<body>`; images `../kb_images/...`; home page entries link `html_pages/<Page>.html`. Only index.html stays in the root (GitHub Pages home page). The site check reports any page outside `html_pages/`. Do not put `<style>` blocks in pages; add shared classes to kb_style.css.
- White background, black Arial text, bold where needed; cards, stat boxes, striped tables (see Tesla.html).
- **No round numbering badges** on cards or boxes (user rule, 2026-10-16).
- Long lists of items: full-width row cards (`.rows` / `.row-card`, see Civilizations_Empires.html): one header line, max 2 text lines, extra details in `<div class="more">` behind the expand icon.
- **Top arrow**: kb_common.js adds a "back to top" arrow (`assets/top_arrow.svg`) to the top-right corner of every page; size and margins in kb_config.js. Nothing to add per page.
- **Expand all**: kb_common.js adds an "Expand all / Collapse all" button automatically to any page with 2+ expandable boxes (right end of `.section-nav`, or under the header). Nothing to add per page; a page may place its own `<button class="expand-all">` instead (see Timeline_of_Humanity.html).
- Home page entries: name on top, description + "Added" date on one single line (CSS cuts long text; full text on hover).
- Create new pages with `tools/new_page.py` (creates them in `html_pages/` and adds the home page entry automatically).
- "kb" means knowledge_bank. **All page images go in `kb_images/`** (one shared folder, published), named with a lowercase page prefix, e.g. `tesla_model_s.png`, `periodic_table.png`. No per-page image folders. Originals may stay in `data/`, but `data/` is never published, so pages must not link to it. File and folder names are case-sensitive on GitHub.
- Run the site check before publishing.
- American spelling. Python: PEP 8, type hints, docstrings, pathlib, paths resolved from the project folder; tools must work under pythonw.exe (no print dependency in GUI code).
- After every change, run the site check and tests, then commit and push to `origin main` without asking (user rule, 2026-10-17). Ask only when there is an open question or a check/test fails. Do not start the preview window without the user's authorization.

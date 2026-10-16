# KNOWLEDGE\_BANK APP



###### FUNCTION: JCR Knowledge Bank static website (GitHub Pages) with development tools

######

###### Filename: "main.py" (local preview), "index.html" (home page)

###### Folder: "C:\\Users\\Jerome\\PYTHON\_PROJECTS\\knowledge\_bank"

###### Date Created: 20261016

###### Created by: JR / Claude



### App Description \& Operation:

1. The website is a home page (index.html, "JCR KNOWLEDGE BANK") with an alphabetical list of knowledge pages. Tesla.html is the first page.
2. All pages share one style (assets/kb_style.css) and have a return arrow (top left) back to the home page. Arrow size and margins are set in kb_config.js.
3. New page: VS Code task "KB: New page" (or tools/new_page.py) creates the page from the template and adds it to the home page list.
4. Preview: the knowledge\_bank shortcut starts a local server that behaves like GitHub Pages (case-sensitive) and opens the site in the browser. CHECK SITE finds broken links/images.
5. Publish: commit and push in VS Code Source Control; the live site updates in 1-2 minutes.



#### CLAUDE App Setup Description:

Created .venv (Python 3.14) with pytest and Pillow; git repository linked to github.com/jeromecharlesrenard-collab/knowledge\_bank; shared stylesheet and script in assets\\; page template; tools\\ (new\_page, site\_check, preview, kb\_core); tests\\ (pytest); config.json; logs\\app.log (1 MB x 5); .vscode settings, extensions, and tasks; .editorconfig, .gitignore, .gitattributes, .nojekyll; CLAUDE.md; knowledge\_bank.lnk shortcut.



##### 20261016 Update



1\. Initial development environment setup.



##### Next Update

endfile

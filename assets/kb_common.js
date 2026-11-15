// JCR Knowledge Bank - shared page script.
// Load in <head> right after kb_config.js.

// Site root folder, from this script's own address (pages sit in html_pages/, the home page at the root).
var KB_ROOT = (function () {
  var s = document.currentScript;
  return s ? s.src.replace(/assets\/kb_common\.js(\?.*)?$/, '') : '';
})();

// Apply return arrow settings from kb_config.js (defaults used if the file is missing).
(function () {
  var c = window.KB_CONFIG || {};
  var root = document.documentElement.style;
  root.setProperty('--ra-size', ((c.returnArrowSize || 100) / 100 * 48) + 'px');
  root.setProperty('--ra-top', (c.returnArrowTopMargin != null ? c.returnArrowTopMargin : 18) + 'pt');
  root.setProperty('--ra-left', (c.returnArrowLeftMargin != null ? c.returnArrowLeftMargin : 18) + 'pt');
  root.setProperty('--ta-size', ((c.topArrowSize || 100) / 100 * 48) + 'px');
  root.setProperty('--ta-top', (c.topArrowTopMargin != null ? c.topArrowTopMargin : 18) + 'pt');
  root.setProperty('--ta-right', (c.topArrowRightMargin != null ? c.topArrowRightMargin : 18) + 'pt');
})();

// Top arrow (top-right corner): added to every page; scrolls smoothly back to the top.
document.addEventListener('DOMContentLoaded', function () {
  if (document.querySelector('.top-arrow')) { return; }
  var a = document.createElement('a');
  a.className = 'top-arrow';
  a.href = '#';
  a.title = 'Back to top';
  a.setAttribute('aria-label', 'Back to top');
  a.innerHTML = '<img src="' + KB_ROOT + 'assets/top_arrow.svg" alt="">';
  a.addEventListener('click', function (event) {
    event.preventDefault();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    // Drop a section link (#other) from the address so a refresh stays at the top.
    if (window.location.hash && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  });
  document.body.insertBefore(a, document.body.firstChild);
});

// Row cards: add an expand icon to cards with hidden content (cut-off text or a .more block).
(function () {
  var CHEVRON = '<svg viewBox="0 0 12 12" aria-hidden="true"><polyline points="2,4 6,8 10,4" ' +
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function hasHiddenContent(card) {
    if (card.querySelector('.more')) { return true; }
    var desc = card.querySelector('.desc');
    if (desc && desc.scrollHeight > desc.clientHeight + 1) { return true; }
    var cells = card.querySelectorAll('.row-head h3, .fact');
    for (var i = 0; i < cells.length; i++) {
      if (cells[i].scrollWidth > cells[i].clientWidth + 1) { return true; }
    }
    return false;
  }

  function update() {
    var cards = document.querySelectorAll('.row-card');
    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var btn = card.querySelector('.expand-btn');
      if (!btn) {
        btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'expand-btn';
        btn.innerHTML = CHEVRON;
        btn.addEventListener('click', function (event) {
          var c = event.currentTarget.parentNode;
          var open = c.classList.toggle('expanded');
          event.currentTarget.setAttribute('aria-expanded', open ? 'true' : 'false');
          event.currentTarget.title = open ? 'Show less' : 'Show more';
          syncExpandAll();
        });
        btn.setAttribute('aria-expanded', 'false');
        btn.title = 'Show more';
        card.appendChild(btn);
        // Title boxes: clicking the title line also toggles the box.
        var line = card.querySelector('.title-line');
        if (line) {
          line.addEventListener('click', function (event) {
            event.currentTarget.parentNode.querySelector('.expand-btn').click();
          });
        }
      }
      if (!card.classList.contains('expanded')) {
        btn.hidden = !hasHiddenContent(card);
      }
    }
    syncExpandAll();
  }

  // "Expand all" button: added automatically to every page with expandable boxes.
  // Placed at the right end of the section links (.section-nav), or under the header.
  // A page can place its own <button class="expand-all"> instead.
  function expandableCards() {
    var result = [];
    var cards = document.querySelectorAll('.row-card');
    for (var i = 0; i < cards.length; i++) {
      var btn = cards[i].querySelector('.expand-btn');
      if (btn && (!btn.hidden || cards[i].classList.contains('expanded'))) { result.push(cards[i]); }
    }
    return result;
  }

  function anyClosed(cards) {
    for (var i = 0; i < cards.length; i++) {
      if (!cards[i].classList.contains('expanded')) { return true; }
    }
    return false;
  }

  function syncExpandAll() {
    var all = document.querySelector('.expand-all');
    if (!all) { return; }
    var cards = expandableCards();
    all.hidden = cards.length < 2;
    all.textContent = anyClosed(cards) ? 'Expand all' : 'Collapse all';
  }

  function addExpandAll() {
    if (!document.querySelector('.row-card')) { return; }
    var all = document.querySelector('.expand-all');
    if (!all) {
      all = document.createElement('button');
      all.type = 'button';
      all.className = 'expand-all';
      all.textContent = 'Expand all';
      var nav = document.querySelector('.section-nav');
      var header = document.querySelector('.page > header');
      if (nav) {
        nav.appendChild(all);
      } else if (header) {
        var bar = document.createElement('div');
        bar.className = 'expand-all-bar';
        bar.appendChild(all);
        header.parentNode.insertBefore(bar, header.nextSibling);
      } else {
        return;
      }
    }
    all.addEventListener('click', function () {
      var cards = expandableCards();
      var open = anyClosed(cards);
      for (var i = 0; i < cards.length; i++) {
        if (cards[i].classList.contains('expanded') !== open) {
          cards[i].querySelector('.expand-btn').click();
        }
      }
      syncExpandAll();
    });
  }

  document.addEventListener('DOMContentLoaded', addExpandAll);

  var timer = null;
  document.addEventListener('DOMContentLoaded', update);
  window.addEventListener('load', update);
  window.addEventListener('resize', function () {
    clearTimeout(timer);
    timer = setTimeout(update, 150);
  });
})();

// Home page: sort index entries alphabetically and group them under letter headings.
document.addEventListener('DOMContentLoaded', function () {
  var source = document.getElementById('entries');
  if (!source) { return; }
  var nameOf = function (item) { return item.querySelector('.name').textContent.trim(); };
  var items = Array.prototype.slice.call(source.querySelectorAll('.entry'));
  items.sort(function (a, b) {
    return nameOf(a).localeCompare(nameOf(b), 'en', { sensitivity: 'base' });
  });
  var container = source.parentNode;
  container.removeChild(source);
  var currentLetter = null, list = null;
  items.forEach(function (item) {
    var letter = nameOf(item).charAt(0).toUpperCase();
    if (letter !== currentLetter) {
      currentLetter = letter;
      var heading = document.createElement('h2');
      heading.className = 'letter';
      heading.textContent = letter;
      container.appendChild(heading);
      list = document.createElement('ul');
      list.className = 'list';
      container.appendChild(list);
    }
    list.appendChild(item);
  });
});

// Site search: a box on every page (right of the title; under the subtitle on the home page).
// The pages listed on the home page are read on first use, so the search is always up to date
// with no index file to rebuild. Needs http(s): the live site or the local preview.
// A result opens its page with ?q=<words>&b=<block>: the words are highlighted, the box holding
// them is expanded, and the page scrolls to it.
var KB_SEARCH = (function () {
  var CACHE_KEY = 'kb-search-v1';
  var CACHE_MINUTES = 10;
  var MAX_RESULTS = 40;
  var site = null; // promise of [{name, href, blocks: [{title, text}]}]

  // Lowercase, accents removed, one character per character (positions match the original text).
  function fold(text) {
    var out = '';
    for (var i = 0; i < text.length; i++) {
      var c = text.charAt(i).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
      out += c.length === 1 ? c : text.charAt(i).toLowerCase().charAt(0);
    }
    return out;
  }

  function clean(text) { return (text || '').replace(/\s+/g, ' ').trim(); }

  // Searchable blocks of a page, in page order: each box (article.card) is one block; text
  // outside boxes (paragraphs, list items, table rows) is one block per element.
  function blocksOf(root) {
    var blocks = [];
    var section = '';
    var els = root.querySelectorAll('h2, article.card, p, li, tr, figure, dt');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.closest('header, footer, nav, .kb-search')) { continue; }
      if (el.tagName === 'H2') { section = clean(el.textContent); continue; }
      if (el.tagName !== 'ARTICLE' && el.closest('article.card')) { continue; }
      var title = section;
      if (el.tagName === 'ARTICLE') {
        var h3 = el.querySelector('h3');
        if (h3) { title = (section ? section + ' › ' : '') + clean(h3.textContent); }
      }
      var text = clean(el.textContent);
      if (text) { blocks.push({ title: title, text: text, el: el }); }
    }
    return blocks;
  }

  function loadSite() {
    if (site) { return site; }
    try {
      var cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || 'null');
      if (cached && Date.now() - cached.time < CACHE_MINUTES * 60000) {
        site = Promise.resolve(cached.pages);
        return site;
      }
    } catch (e) { /* no storage: read the pages */ }
    var parser = new DOMParser();
    var get = function (href) {
      return fetch(KB_ROOT + href, { cache: 'no-store' }).then(function (r) {
        if (!r.ok) { throw new Error(href + ': ' + r.status); }
        return r.text();
      }).then(function (html) { return parser.parseFromString(html, 'text/html'); });
    };
    site = get('index.html').then(function (home) {
      var links = home.querySelectorAll('#entries .entry a');
      return Promise.all(Array.prototype.map.call(links, function (a) {
        var href = a.getAttribute('href');
        var name = clean(a.querySelector('.name') ? a.querySelector('.name').textContent : href);
        return get(href).then(function (doc) {
          var blocks = blocksOf(doc.querySelector('.page') || doc.body).map(function (b) {
            return { title: b.title, text: b.text };
          });
          return { name: name, href: href, blocks: blocks };
        }).catch(function () { return { name: name, href: href, blocks: [] }; });
      }));
    }).then(function (pages) {
      try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ time: Date.now(), pages: pages })); } catch (e) { /* full */ }
      return pages;
    }, function (err) { site = null; throw err; });
    return site;
  }

  function termsOf(query) {
    return fold(clean(query)).split(' ').filter(function (t) { return t.length > 0; });
  }

  // Matches: blocks containing every word of the query.
  function search(query) {
    var terms = termsOf(query);
    return loadSite().then(function (pages) {
      var results = [];
      if (!terms.length) { return results; }
      pages.forEach(function (page) {
        page.blocks.forEach(function (block, index) {
          var folded = fold(block.text);
          for (var t = 0; t < terms.length; t++) {
            if (folded.indexOf(terms[t]) < 0) { return; }
          }
          results.push({ page: page, block: block, index: index, at: folded.indexOf(terms[0]) });
        });
      });
      return results;
    });
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  // Start and end of each match of the words in text.
  function ranges(text, terms) {
    var folded = fold(text);
    var found = [];
    terms.forEach(function (term) {
      var from = 0, at;
      while (term && (at = folded.indexOf(term, from)) >= 0) {
        found.push([at, at + term.length]);
        from = at + term.length;
      }
    });
    found.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    found.forEach(function (r) {
      var last = merged[merged.length - 1];
      if (last && r[0] <= last[1]) { last[1] = Math.max(last[1], r[1]); } else { merged.push(r); }
    });
    return merged;
  }

  function snippet(text, at, terms) {
    var start = Math.max(0, at - 60), end = Math.min(text.length, at + 120);
    var part = text.slice(start, end);
    var html = '', pos = 0;
    ranges(part, terms).forEach(function (r) {
      html += escapeHtml(part.slice(pos, r[0])) + '<mark>' + escapeHtml(part.slice(r[0], r[1])) + '</mark>';
      pos = r[1];
    });
    html += escapeHtml(part.slice(pos));
    return (start > 0 ? '…' : '') + html + (end < text.length ? '…' : '');
  }

  function resultUrl(r, query) {
    return KB_ROOT + r.page.href + '?q=' + encodeURIComponent(query) + '&b=' + r.index;
  }

  // ----- search box -----

  function addBox() {
    var header = document.querySelector('.page > header');
    if (!header || header.querySelector('.kb-search')) { return; }
    var box = document.createElement('div');
    box.className = 'kb-search';
    box.setAttribute('role', 'search');
    box.innerHTML = '<input type="search" placeholder="Search the knowledge bank" aria-label="Search the knowledge bank" ' +
      'autocomplete="off" spellcheck="false"><div class="kb-results" hidden></div>';
    var h1 = header.querySelector('h1');
    if (document.body.classList.contains('home') || !h1) {
      header.appendChild(box);
    } else {
      var row = document.createElement('div');
      row.className = 'header-row';
      header.insertBefore(row, h1);
      row.appendChild(h1);
      row.appendChild(box);
    }
    var input = box.querySelector('input');
    var panel = box.querySelector('.kb-results');
    var timer = null, current = [], query = '';

    function show(html) { panel.innerHTML = html; panel.hidden = !html; }

    function run() {
      query = input.value;
      if (clean(query).length < 2) { current = []; show(''); return; }
      var asked = query;
      search(asked).then(function (results) {
        if (asked !== input.value) { return; }
        current = results;
        var terms = termsOf(asked);
        if (!results.length) { show('<p class="kb-note">No match for “' + escapeHtml(clean(asked)) + '”.</p>'); return; }
        var html = '<p class="kb-note">' + results.length + ' match' + (results.length === 1 ? '' : 'es') +
          (results.length > MAX_RESULTS ? ' (first ' + MAX_RESULTS + ' shown)' : '') + '</p>';
        results.slice(0, MAX_RESULTS).forEach(function (r) {
          html += '<a class="kb-result" href="' + escapeHtml(resultUrl(r, clean(asked))) + '">' +
            '<span class="kb-where"><b>' + escapeHtml(r.page.name) + '</b>' +
            (r.block.title ? ' › ' + escapeHtml(r.block.title) : '') + '</span>' +
            '<span class="kb-snip">' + snippet(r.block.text, r.at, terms) + '</span></a>';
        });
        show(html);
      }, function () {
        show('<p class="kb-note">Search needs the website: open it online or with the local preview ' +
             '(KNOWLEDGE BANK L), not as a file.</p>');
      });
    }

    input.addEventListener('focus', function () { loadSite().catch(function () {}); if (panel.innerHTML) { panel.hidden = false; } });
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 150); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && current.length) { window.location.href = resultUrl(current[0], clean(input.value)); }
      if (e.key === 'Escape') { panel.hidden = true; input.blur(); }
    });
    document.addEventListener('click', function (e) { if (!box.contains(e.target)) { panel.hidden = true; } });

    var asked = new URLSearchParams(window.location.search).get('q');
    if (asked) { input.value = asked; }
  }

  // ----- arriving from a result: highlight, expand, scroll -----

  function highlight() {
    var params = new URLSearchParams(window.location.search);
    var terms = termsOf(params.get('q') || '');
    if (!terms.length) { return; }
    var root = document.querySelector('.page') || document.body;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        var p = node.parentNode;
        if (!node.nodeValue.trim() || p.closest('script, style, header, .kb-search, mark')) { return NodeFilter.FILTER_REJECT; }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [];
    while (walker.nextNode()) { nodes.push(walker.currentNode); }
    var marks = [];
    nodes.forEach(function (node) {
      var text = node.nodeValue, found = ranges(text, terms);
      if (!found.length) { return; }
      var frag = document.createDocumentFragment(), pos = 0;
      found.forEach(function (r) {
        frag.appendChild(document.createTextNode(text.slice(pos, r[0])));
        var mark = document.createElement('mark');
        mark.className = 'kb-hit';
        mark.textContent = text.slice(r[0], r[1]);
        frag.appendChild(mark);
        marks.push(mark);
        pos = r[1];
      });
      frag.appendChild(document.createTextNode(text.slice(pos)));
      node.parentNode.replaceChild(frag, node);
    });
    // Open every box that holds a match.
    marks.forEach(function (mark) {
      var card = mark.closest('.row-card');
      if (card && !card.classList.contains('expanded')) {
        var btn = card.querySelector('.expand-btn');
        if (btn) { btn.click(); } else { card.classList.add('expanded'); }
      }
    });
    // Scroll to the result that was clicked (block b), else to the first match.
    var target = null, b = parseInt(params.get('b'), 10);
    if (!isNaN(b)) {
      var block = blocksOf(root)[b];
      if (block) { target = block.el.querySelector('mark.kb-hit') || block.el; }
    }
    target = target || marks[0];
    if (target) { target.scrollIntoView({ block: 'center' }); }
  }

  document.addEventListener('DOMContentLoaded', addBox);
  window.addEventListener('load', highlight);
  return { search: search, blocksOf: blocksOf };
})();

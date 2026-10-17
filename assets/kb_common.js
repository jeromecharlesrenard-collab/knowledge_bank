// JCR Knowledge Bank - shared page script.
// Load in <head> right after kb_config.js.

// Apply return arrow settings from kb_config.js (defaults used if the file is missing).
(function () {
  var c = window.KB_CONFIG || {};
  var root = document.documentElement.style;
  root.setProperty('--ra-size', ((c.returnArrowSize || 100) / 100 * 48) + 'px');
  root.setProperty('--ra-top', (c.returnArrowTopMargin != null ? c.returnArrowTopMargin : 18) + 'pt');
  root.setProperty('--ra-left', (c.returnArrowLeftMargin != null ? c.returnArrowLeftMargin : 18) + 'pt');
})();

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
  }

  // "Expand all" button: opens every box, or closes them all when all are open.
  document.addEventListener('DOMContentLoaded', function () {
    var all = document.querySelector('.expand-all');
    if (!all) { return; }
    all.addEventListener('click', function () {
      var cards = document.querySelectorAll('.row-card');
      var open = false;
      for (var i = 0; i < cards.length; i++) {
        if (!cards[i].classList.contains('expanded')) { open = true; }
      }
      for (var j = 0; j < cards.length; j++) {
        var btn = cards[j].querySelector('.expand-btn');
        if (btn && !btn.hidden && cards[j].classList.contains('expanded') !== open) { btn.click(); }
      }
      all.textContent = open ? 'Collapse all' : 'Expand all';
    });
  });

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

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

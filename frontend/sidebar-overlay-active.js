(function () {
  var overlaySelectors = [
    'a[id="openHistoryOverlay"]',
    'a[id="openFavoritesOverlay"]',
    'a[id="openReportsOverlay"]',
    'a[id="openAdminReportsOverlay"]'
  ];

  function detectMode(nav) {
    if (nav.querySelector('a.nav-active')) return 'nav-active';
    if (nav.querySelector('a.active')) return 'active';
    return 'emerald';
  }

  function applyActiveState(trigger) {
    if (!trigger) return;
    var nav = trigger.closest('nav');
    if (!nav) return;

    var links = Array.prototype.slice.call(nav.querySelectorAll('a'));
    if (!links.length) return;

    var mode = detectMode(nav);
    var shouldUseShadow = links.some(function (a) {
      return a.classList.contains('bg-emerald-700') && a.classList.contains('shadow-lg');
    });

    links.forEach(function (a) {
      a.classList.remove('nav-active');
      a.classList.remove('active');
      a.classList.remove('bg-emerald-700');
      a.classList.remove('text-white');
      a.classList.remove('shadow-lg');
    });

    if (mode === 'nav-active') {
      trigger.classList.add('nav-active');
      return;
    }

    if (mode === 'active') {
      trigger.classList.add('active');
      return;
    }

    trigger.classList.add('bg-emerald-700');
    trigger.classList.add('text-white');
    if (shouldUseShadow) trigger.classList.add('shadow-lg');
  }

  overlaySelectors.forEach(function (selector) {
    var links = document.querySelectorAll(selector);
    links.forEach(function (link) {
      link.addEventListener('click', function () {
        applyActiveState(link);
      });
    });
  });
})();

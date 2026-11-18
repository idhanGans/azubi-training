// devdesk-integration: web loader v2 file (coding-platform docs/devdesk-integration/web/cp-devdesk.js)
// The ONE Dev-Desk loader. `loader.html` and `loader-always.html` carry this exact body
// inline (tests/test_devdesk_loader.py keeps them in sync); a page that must not have
// inline scripts vendors this file unchanged and includes it SYNCHRONOUSLY in <head>,
// before the app's own scripts: <script src="/cp-devdesk.js" data-slug=… data-domain=…></script>
// Config = data attributes of its own <script> tag (INTEGRATION.md §2):
//   data-slug     MSH slug of the service (required)
//   data-domain   $MSH_PLATFORM_DOMAIN (required)
//   data-modes    modes that load WITHOUT a mode link, comma list of user,release,main
//                 (default "user"); any other mode of the service only via the CP mode link
//   data-main     what the main host (<slug>) loads: deck (default) | headless
//                 (/rec/recorder-headless.js: Desk tracking, no deck/hotkey/mic) | none
// Hosts: main <slug>, release release-<slug>, user <user>[-<slot>]-<slug>; others never.
// A preset window.__cpRec (`devdesk: none` page guard) loads nothing.
(function () {
  var el = document.currentScript, c = (el && el.dataset) || {};
  var SLUG = c.slug || '', DOMAIN = c.domain || '', K = 'cp-rec';
  var MODES = ',' + String(c.modes || 'user').replace(/\s+/g, '') + ',', MAIN = c.main || 'deck';
  var host = location.hostname, sfx = '.' + DOMAIN;
  if (!SLUG || !DOMAIN || location.protocol !== 'https:' || host.slice(-sfx.length) !== sfx) return;
  var label = host.slice(0, -sfx.length);
  if (label.indexOf('.') >= 0) return;
  var mode = label === SLUG ? 'main' : label === 'release-' + SLUG ? 'release'
    : label.slice(-(SLUG.length + 1)) === '-' + SLUG ? 'user' : '';
  if (!mode) return;
  var ss = null;
  try { ss = window.sessionStorage; } catch (e) { ss = null; }
  var m = /(^#|&)cp_rec=([A-Za-z0-9_-]{20,})$/.exec(location.hash);
  if (m) {
    if (!ss) return;
    if (ss.getItem(K) !== m[2]) { ss.removeItem(K + '-seq'); ss.removeItem(K + '-take'); }
    ss.setItem(K, m[2]);
    ss.removeItem(K + '-auto');
    ss.removeItem(K + '-off');
    var rest = location.hash.slice(0, m.index);
    history.replaceState(history.state, '', location.pathname + location.search + (rest === '#' ? '' : rest));
  }
  var file = mode !== 'main' || MAIN === 'deck' ? 'recorder.js' : MAIN === 'headless' ? 'recorder-headless.js' : '';
  var linked = !!(ss && ss.getItem(K)) || /[?&]cp_rec=/.test(location.search);
  if (!file || (MODES.indexOf(',' + mode + ',') < 0 && !linked) || window.__cpRec) return;
  var s = document.createElement('script');
  s.src = 'https://coding-platform.' + DOMAIN + '/rec/' + file;
  s.async = true;
  document.head.appendChild(s);
})();

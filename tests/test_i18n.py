"""UI texts: each key exactly once (a second one silently overwrites the first) and in DE/EN/ID.
The texts live in i18n.js and thematic extensions i18n_<theme>.js (Object.assign onto I18N)."""
import glob
import os
import re

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'static', 'js')
I18N_FILES = [os.path.join(JS, 'i18n.js'), *sorted(glob.glob(os.path.join(JS, 'i18n_*.js')))]
ENTRY = re.compile(r"^  ([a-zA-Z0-9_]+):\{(.*)\},?$")


def _entries():
    entries = []
    for path in I18N_FILES:
        with open(path, encoding='utf-8') as fh:
            entries += [m.groups() for m in (ENTRY.match(line.rstrip('\n')) for line in fh) if m]
    return entries


def test_ergaenzungen_werden_geladen():
    with open(os.path.join(os.path.dirname(JS), '..', 'templates', 'base.html'), encoding='utf-8') as fh:
        base = fh.read()
    for path in I18N_FILES:
        assert f"filename='js/{os.path.basename(path)}'" in base


def test_schluessel_eindeutig():
    keys = [k for k, _ in _entries()]
    doppelt = sorted({k for k in keys if keys.count(k) > 1})
    assert not doppelt, f'doppelte Schluessel: {doppelt}'
    assert len(keys) > 600


def test_jede_sprache_vorhanden():
    fehlend = [k for k, body in _entries() if not all(re.search(rf"\b{lang}:['\"]", body) for lang in ('de', 'en', 'id'))]
    assert not fehlend, f'ohne de/en/id: {fehlend}'


APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app')
#: Places where a key appears literally: t('x') / t(a ? 'x' : 'y'), data-i18n(-aria)="x",
#: page titles (_page/page_i18n) and navigation (NavItem). Composite keys ('ss_' + status) not included.
_T_CALL = re.compile(r"\bt\(([^()]*?)(?:,|\))")
_LITERAL = re.compile(r"(?<!= )(?<!=)'([a-z][a-zA-Z0-9_]*)'(?!\s*\+)")    # not: x === 'file'
_ATTR = re.compile(r'data-i18n(?:-aria)?="([a-zA-Z0-9_]+)"')
_PY = re.compile(r"(?:_page\('[^']+', '[^']+', |page_i18n=|NavItem\('[^']+', )'([a-zA-Z0-9_]+)'")
_KEY_MAP = re.compile(r"_KEYS = \{([^}]*)\}")


def test_jeder_benutzte_schluessel_existiert():
    """A missing key otherwise appears raw in the UI (e.g. "dlg_course_add" as a dialog title)."""
    known = {k for k, _ in _entries()}
    used = {}
    for root, _dirs, files in os.walk(APP):
        for name in files:
            path = os.path.join(root, name)
            if re.fullmatch(r'i18n(_\w+)?\.js', name) or not name.endswith(('.js', '.html', '.py')):
                continue
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            found = set(_ATTR.findall(text))
            if name.endswith('.js'):
                for arg in _T_CALL.findall(text):
                    if '+' not in arg and '`' not in arg:
                        found |= set(_LITERAL.findall(arg))
                for block in _KEY_MAP.findall(text):
                    found |= set(_LITERAL.findall(block))
            if name.endswith('.py'):
                found |= set(_PY.findall(text))
            for key in found - known:
                used.setdefault(key, os.path.relpath(path, APP))
    assert not used, f'Schluessel fehlen in i18n.js: {used}'


#: Emojis and pictographic characters (🎓 ✅ 🔒 ☰ ◀ …) — symbols come only from static/icons.svg.
#: Typographic arrows (→) and the sort triangles ▲▼ of table headers remain allowed.
_EMOJI = re.compile('[←↑↓-⇿⌀-⏿■-▱△-▻▽-◿'
                    '☀-➿⬀-⯿\U0001F000-\U0001FAFF️]')


def test_keine_emojis_in_der_oberflaeche():
    found = []
    for root, _dirs, files in os.walk(APP):
        for name in files:
            if not name.endswith(('.js', '.html', '.py', '.css')):
                continue
            path = os.path.join(root, name)
            with open(path, encoding='utf-8') as fh:
                for number, line in enumerate(fh, 1):
                    if _EMOJI.search(line):
                        found.append(f'{os.path.relpath(path, APP)}:{number}')
    assert not found, f'Emojis statt Symbolen aus icons.svg: {found}'

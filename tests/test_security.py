"""Sicherheit (Phase 14): ohne Anmeldung nichts, kaputte Eingaben nie 500, CSRF, Header, Fehlerseiten,
Kandidat A nie Kandidat B, Dozenten nur eigene Datensaetze, SQL-Injection wirkungslos."""
import json
import re
from urllib.parse import urlencode
from datetime import timedelta

import pytest

from app.services.local_time import today

GARBAGE = [
    {},
    {'name': ['x'], 'trainee_id': {'a': 1}, 'template_id': 'abc', 'course_id': -5, 'level_id': 'x', 'date': 'gestern',
     'start': '25:99', 'end': None, 'scores': 'viele', 'entries': {'x': 1}, 'categories': 'x', 'trainee_ids': 'alle',
     'status': 12, 'points': 'drei', 'passing_percent': 'hoch', 'email': 'kein@', 'phone': '<script>',
     'learning_objectives': 'x', 'availability': 'immer', 'level_ids': [None, 'a'], 'skills': ['x'],
     'assessed_on': '31.12.2026', 'from': '2026-13-45', 'repeat_until': 'nie', 'minutes_late': 1e30},
    {'name': 'x' * 100000, 'description': 'y' * 100000, 'note': 'z' * 100000},
]


@pytest.fixture
def world(as_user, grant, trainee):
    """Je ein Datensatz jeder Art mit ID 1 (Kurs Maria) und ein zweiter Kurs (Tom) fuer die Reichweite."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    admin.post('/api/programs', json={'name': 'P'})
    cur = admin.post('/api/programs/1/curricula', json={'level_id': b1}).get_json()['id']
    mod = admin.post(f'/api/curricula/{cur}/modules', json={'name': 'M1'}).get_json()['id']
    admin.upload(f'/api/modules/{mod}/materials', {'type': 'PDF', 'title': 'Skript'}, 's.pdf', b'%PDF-1.4 x')
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [b1]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    anna, bert = trainee('Anna', msh_user='anna'), trainee('Bert', msh_user='bert')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'instructor_id': ids['maria'],
                                          'module_id': mod}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1, 'instructor_id': ids['tom'],
                                          'module_id': mod}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [anna]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [bert]})
    past = (today() - timedelta(days=1)).isoformat()
    s1 = admin.post('/api/sessions', json={'course_id': k1, 'date': past, 'start': '09:00', 'end': '10:00'}
                    ).get_json()['sessions'][0]['id']
    s2 = admin.post('/api/sessions', json={'course_id': k2, 'date': past, 'start': '11:00', 'end': '12:00'}
                    ).get_json()['sessions'][0]['id']
    tpl = admin.post('/api/assessment-templates', json={'name': 'T', 'passing_percent': 60, 'categories': [
        {'name': 'Lesen', 'max_score': 10, 'weight': 1}]}).get_json()
    a_bert = admin.post('/api/assessments', json={'trainee_id': bert, 'template_id': tpl['id'],
                                                  'instructor_id': ids['tom'], 'assessed_on': past}
                        ).get_json()['assessment']['id']
    as_user('bert').post('/api/training/me', json={'period': past, 'hours': 2})
    as_user('bert').get('/api/notifications')
    return {'admin': admin, 'anna': as_user('anna'), 'maria': as_user('maria'), 'k2': k2, 's1': s1, 's2': s2,
            'bert': bert, 'a_bert': a_bert, 'tpl': tpl['id']}


def _url(rule, value='1'):
    return re.sub(r'<(?:\w+:)?(\w+)>', value, rule.rule)


def _write_rules(app):
    return [(r, m) for r in app.url_map.iter_rules() for m in r.methods - {'GET', 'HEAD', 'OPTIONS'}]


def test_kaputte_eingaben_nie_500(app, world):
    admin = world['admin']
    for rule, method in _write_rules(app):
        for body in GARBAGE:
            res = admin._call(method, _url(rule), json=body)
            assert res.status_code < 500, f'{method} {rule.rule} {str(body)[:60]} -> {res.status_code}'
        for raw in ('[1, 2]', '"text"', '42', '{kaputt'):
            res = admin._c.open(_url(rule), method=method, data=raw,
                                headers={'Authorization': 'Bearer root_admin', 'Content-Type': 'application/json'})
            assert res.status_code == 400, f'{method} {rule.rule} {raw} -> {res.status_code}'


def test_kaputte_filter_nie_500(app, world):
    garbage = ('from=2026-13-45&to=gestern&limit=abc&page=-1&per_page=99999&status=zzz&course_id=abc&level_id=-1'
               '&sort=zzz&q=%27%20OR%201%3D1%20--&trainee_id=x&before_id=0&view=x&date=x&archived=2&format=xml&table=x')
    for rule in app.url_map.iter_rules():
        if 'GET' in rule.methods and rule.rule.startswith('/api/'):
            res = world['admin'].get(f'{_url(rule)}?{garbage}')
            assert res.status_code < 500, f'GET {rule.rule} -> {res.status_code}'


def test_ohne_anmeldung_nichts(app, world, as_user):
    anonymous = as_user(None)
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static' or rule.endpoint.startswith('msh_health.'):
            continue
        for method in rule.methods - {'HEAD', 'OPTIONS'}:
            res = anonymous._call(method, _url(rule), json={} if method != 'GET' else None)
            assert res.status_code in (401, 302), f'{method} {rule.rule} -> {res.status_code}'
    assert as_user('kaputt').get('/api/me').status_code == 401


def test_csrf_nur_json_oder_fetch_header(world):
    c = world['admin']._c
    auth = {'Authorization': 'Bearer root_admin'}
    assert c.post('/api/candidates', data={'name': 'X'}, headers=auth).status_code == 415          # Formular
    assert c.post('/api/candidates', data='{"name": "X"}', headers={**auth, 'Content-Type': 'text/plain'}
                  ).status_code == 415
    assert c.post('/api/candidates', data={'name': 'X'}, headers={**auth, 'X-Requested-With': 'fetch'}
                  ).status_code != 415                                                           # Upload-Weg


def test_sicherheits_header(world):
    page = world['admin'].get('/candidates', headers={'Accept': 'text/html'})
    csp = page.headers['Content-Security-Policy']
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert page.headers['X-Content-Type-Options'] == 'nosniff' and page.headers['X-Frame-Options'] == 'DENY'
    api = world['admin'].get('/api/candidates')
    assert api.headers['Cache-Control'] == 'no-store' and 'Content-Security-Policy' not in api.headers
    pdf = world['admin'].get('/api/materials/1/file')
    assert pdf.mimetype == 'application/pdf' and 'Content-Security-Policy' not in pdf.headers   # PDF-Ansicht bleibt


def test_fehler_auf_deutsch_ohne_interna(app, world, monkeypatch):
    res = world['admin'].get('/api/gibt-es-nicht')
    assert res.status_code == 404 and res.get_json() == {'error': 'Die Seite oder der Datensatz wurde nicht gefunden.',
                                                         'code': 'HTTP_404'}
    page = world['admin'].get('/gibt-es-nicht', headers={'Accept': 'text/html'})
    assert page.status_code == 404 and 'nicht gefunden' in page.get_data(as_text=True)
    assert world['admin']._call('DELETE', '/api/candidates').status_code == 405
    from app.services import dashboard
    monkeypatch.setattr(dashboard, 'overview', lambda identity: 1 / 0)
    res = world['admin'].get('/api/dashboard')
    body = res.get_data(as_text=True)
    assert res.status_code == 500 and 'ZeroDivision' not in body and 'Traceback' not in body
    assert res.get_json()['error'].startswith('Ein interner Fehler')


def test_kandidat_a_nie_kandidat_b(world, as_user):
    anna, w = world['anna'], world
    report_b = as_user('bert').get('/api/training/me').get_json()['reports'][0]['id']
    note_b = as_user('bert').get('/api/notifications').get_json()['notifications'][0]['id']
    assert anna.put(f'/api/training/me/{report_b}', json={'hours': 1}).status_code == 404
    assert anna.post(f'/api/notifications/{note_b}/read').status_code == 404
    for url in (f'/api/candidates/{w["bert"]}', f'/api/candidates/{w["bert"]}/progress', f'/api/assessments/{w["a_bert"]}',
                f'/api/sessions/{w["s2"]}/attendance', f'/api/reports/candidates/{w["bert"]}', f'/candidates/{w["bert"]}'):
        assert anna.get(url, headers={'Accept': 'application/json'}).status_code == 403, url
    text = ''.join(anna.get(u).get_data(as_text=True) for u in ('/api/my-overview', '/api/my-courses', '/api/my-modules',
                                                                '/api/my-schedule', '/api/my-assessments',
                                                                '/api/my-attendance', '/api/my-progress'))
    assert 'Bert' not in text and 'Kurs Tom' not in text


def test_dozent_nur_eigene_datensaetze(world):
    maria, w = world['maria'], world
    fremd = [('GET', f'/api/candidates/{w["bert"]}'), ('GET', f'/api/candidates/{w["bert"]}/progress'),
             ('GET', f'/api/courses/{w["k2"]}'), ('GET', f'/api/sessions/{w["s2"]}'),
             ('GET', f'/api/sessions/{w["s2"]}/attendance'), ('PUT', f'/api/sessions/{w["s2"]}/attendance'),
             ('GET', f'/api/assessments/{w["a_bert"]}'), ('PATCH', f'/api/assessments/{w["a_bert"]}'),
             ('POST', f'/api/assessments/{w["a_bert"]}/finalize'), ('DELETE', f'/api/assessments/{w["a_bert"]}')]
    for method, url in fremd:
        res = maria._call(method, url, json={'entries': [{'trainee_id': w['bert'], 'status': 'PRESENT'}]}
                          if method != 'GET' else None)
        assert res.status_code in (403, 404), f'{method} {url} -> {res.status_code}'
    assert maria.post('/api/assessments', json={'trainee_id': w['bert'], 'template_id': w['tpl'],
                                                'assessed_on': today().isoformat()}).status_code == 400
    assert maria.get(f'/api/ratings?trainee_id={w["bert"]}').get_json()['ratings'] == []
    assert 'Bert' not in json.dumps(maria.get('/api/candidates').get_json())
    assert maria.get(f'/api/sessions/{w["s1"]}/attendance').status_code == 200             # eigener Kurs geht


def test_sql_injection_wirkungslos(world):
    for q in ("' OR 1=1 --", "Anna'; DROP TABLE trainee; --", '%', '_'):
        res = world['admin'].get('/api/candidates?' + urlencode({'q': q}))
        assert res.status_code == 200 and res.get_json()['total'] == 0, q
    assert world['admin'].get('/api/candidates').get_json()['total'] == 2           # Tabelle unversehrt


def test_abmelden_link(world):
    html = world['anna'].get('/my', headers={'Accept': 'text/html'}).get_data(as_text=True)
    assert 'href="https://login.example/logout?redirect=http%3A//localhost/"' in html
    behind_proxy = world['anna'].get('/my', headers={'Accept': 'text/html', 'X-Forwarded-Proto': 'https',
                                                     'X-Forwarded-Host': 'azubi.planville.work'})
    assert 'redirect=https%3A//azubi.planville.work/"' in behind_proxy.get_data(as_text=True)


def test_dev_desk_loader(app, as_user):
    """Dev-Desk loader (coding-platform docs/devdesk-integration, file form): only with the platform domain, then
    the CSP allows exactly coding-platform.<domain> for scripts and connections."""
    from app import security
    assert 'coding-platform' not in security.csp('')
    csp = security.csp('planville.work')
    assert "script-src 'self' https://coding-platform.planville.work;" in csp
    assert "connect-src 'self' https://coding-platform.planville.work wss://coding-platform.planville.work;" in csp
    loader = open(f'{app.root_path}/static/js/cp-devdesk.js', encoding='utf-8').readline()
    assert loader.startswith('// devdesk-integration: web loader v2 file')
    admin = as_user('root_admin')
    before = app.config['PLATFORM_DOMAIN']
    try:
        app.config['PLATFORM_DOMAIN'] = ''
        assert 'cp-devdesk.js' not in admin.get('/candidates', headers={'Accept': 'text/html'}).get_data(as_text=True)
        app.config['PLATFORM_DOMAIN'] = 'planville.work'
        html = admin.get('/candidates', headers={'Accept': 'text/html'}).get_data(as_text=True)
    finally:
        app.config['PLATFORM_DOMAIN'] = before
    head = html[:html.index('</head>')]
    assert 'js/cp-devdesk.js' in head and 'data-slug="azubi-training" data-domain="planville.work"' in head
    assert head.index('cp-devdesk.js') < head.index('app.css')          # synchronous, before everything else

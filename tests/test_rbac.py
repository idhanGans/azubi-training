"""Access rules: every route declares them, every role gets exactly its permissions."""
import re

import pytest

from app import auth


def test_jede_route_hat_eine_zugriffsregel(app):
    offen = {'static'}
    ohne = [rule.rule for rule in app.url_map.iter_rules()
            if rule.endpoint not in offen and not rule.endpoint.startswith('msh_health.')
            and getattr(app.view_functions[rule.endpoint], auth.ACCESS_ATTR, None) is None]
    assert not ohne, f'Routen ohne Zugriffsregel: {ohne}'


def test_login_ohne_rolle_ist_mitarbeiter_und_darf_nur_bewerten(as_user):
    client = as_user('neu_hier')
    assert client.get('/api/me').get_json()['roles'] == ['EVALUATOR']
    for url in ('/api/trainees', '/api/training', '/api/ratings', '/api/reports/attendance',
                '/api/activity', '/api/users', '/api/candidates', '/api/assessments'):
        assert client.get(url).status_code == 403, url
    assert client.get('/api/rating-board').get_json()['trainees'] == []     # without assignment: nobody
    assert client.get('/api/overall').get_json()['rows'] == []
    res = client.get('/', headers={'Accept': 'text/html'})
    assert res.status_code == 302 and res.headers['Location'].endswith('/ratings')


def test_archivierter_kandidat_bekommt_kein_zugriff_seite(as_user, trainee):
    """Without any role, only whoever is archived as a candidate remains — no fallback to "staff member"."""
    tid = trainee('Budi', msh_user='budi')
    as_user('root_admin').post(f'/api/candidates/{tid}/archive')
    client = as_user('budi')
    assert client.get('/api/me').get_json()['roles'] == []
    assert client.get('/api/rating-board').status_code == 403
    res = client.get('/', headers={'Accept': 'text/html'})
    assert res.status_code == 403
    assert 'Kein Zugriff' in res.get_data(as_text=True)


@pytest.mark.parametrize('role,url,erwartet', [
    ('HR', '/api/trainees', 200),
    ('HR', '/api/overall', 200),
    ('HR', '/api/activity', 403),
    ('HR', '/api/users', 403),
    ('INSTRUCTOR', '/api/trainees', 200),
    ('INSTRUCTOR', '/api/ratings', 200),
    ('INSTRUCTOR', '/api/reports/attendance', 403),
    ('MANAGEMENT', '/api/overall', 200),
    ('MANAGEMENT', '/api/activity', 403),
    ('ACADEMIC_MANAGER', '/api/ratings', 200),
    ('SUPER_ADMIN', '/api/activity', 200),
    ('SUPER_ADMIN', '/api/users', 200),
])
def test_lesen_je_rolle(as_user, grant, role, url, erwartet):
    grant('person', role)
    assert as_user('person').get(url).status_code == erwartet


@pytest.mark.parametrize('role,darf_anlegen,darf_bewerten', [
    ('HR', True, True),              # internal team (rating.internal): every active candidate
    ('ACADEMIC_MANAGER', False, False),     # only rates whoever they're assigned to as SPV/leader
    ('INSTRUCTOR', False, False),
    ('MANAGEMENT', False, False),
])
def test_schreiben_je_rolle(as_user, grant, trainee, role, darf_anlegen, darf_bewerten):
    grant('person', role)
    tid = trainee('Budi')
    client = as_user('person')
    res = client.post('/api/candidates', json={'name': 'Neu'})
    assert (res.status_code == 201) is darf_anlegen
    res = client.post('/api/ratings', json={'trainee_id': tid, 'r_practical': 7, 'r_reliability': 7,
                                            'r_motivation': 7})
    assert (res.status_code == 201) is darf_bewerten


def test_mehrere_rollen_ergeben_die_vereinigung(as_user, grant):
    grant('person', 'MANAGEMENT')
    grant('person', 'INSTRUCTOR')
    perms = set(as_user('person').get('/api/me').get_json()['permissions'])
    assert {'report.view', 'attendance.manage'} <= perms


def test_seitenleiste_zeigt_nur_erlaubte_seiten(as_user, grant):
    grant('person', 'MANAGEMENT')
    html = as_user('person').get('/training', headers={'Accept': 'text/html'}).get_data(as_text=True)
    assert 'href="/overall"' in html
    assert 'href="/users"' not in html
    assert 'href="/activity"' not in html


@pytest.mark.parametrize('login,url,erwartet', [
    ('hr', '/candidates', 200),
    ('hr', '/candidates/1', 200),
    ('hr', '/settings', 403),
    ('root_admin', '/settings', 200),
    ('anna', '/candidates', 403),
    ('anna', '/candidates/1', 403),
])
def test_seiten_zugriff(as_user, grant, trainee, login, url, erwartet):
    grant('hr', 'HR')
    trainee('Anna', msh_user='anna')
    assert as_user(login).get(url, headers={'Accept': 'text/html'}).status_code == erwartet


def _url(rule):
    return re.sub(r'<(?:\w+:)?\w+>', '1', rule.rule)


def test_rechte_matrix_jede_route_jede_rolle(app, as_user, grant):
    """Complete instead of a sample: for EVERY route with a permission and EVERY team role it holds —
    if the role lacks the permission, every method responds with 403; if it has it, reading never returns 403.
    Candidate routes are locked for every team role. The basis is solely services/permissions.py."""
    from app.services import permissions
    clients = {}
    for role in permissions.ASSIGNABLE_ROLES:
        grant(f'matrix_{role.lower()}', role)
        clients[role] = as_user(f'matrix_{role.lower()}')
    wrong, checked = [], 0
    for rule in app.url_map.iter_rules():
        access = getattr(app.view_functions[rule.endpoint], auth.ACCESS_ATTR, None)
        if access is None or access[0] not in ('permission', 'candidate'):
            continue
        for role, client in clients.items():
            allowed = access[0] == 'permission' and access[1] in permissions.permissions_for([role])
            for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
                if allowed and method != 'GET':
                    continue                      # writing with permission: business tests per area
                res = client._call(method, _url(rule), json={} if method != 'GET' else None)
                checked += 1
                if (res.status_code == 403) is allowed:
                    wrong.append(f'{role} {method} {rule.rule} -> {res.status_code}')
    assert not wrong, f'{len(wrong)} falsche Antworten, z.B. {wrong[:10]}'
    assert checked > 450                          # currently 498 combinations

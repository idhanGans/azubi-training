"""Team-Dashboard: Kennzahlen-Definitionen, Reichweite der Dozenten, Handlungsbedarf nur mit passendem Recht."""
from datetime import timedelta

import pytest

from app.services.local_time import today


@pytest.fixture
def dash(as_user, grant, trainee):
    """Kurs Maria (RUNNING, Modul 2 von 4): Budi + Sari; Kurs Tom (PLANNED): Dewi; Eko ohne Kurs."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    admin.post('/api/programs', json={'name': 'Sprechkurs'})
    pid = admin.get('/api/programs').get_json()['programs'][0]['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    mods = [admin.post(f'/api/curricula/{cur}/modules', json={'name': f'M{n}'}).get_json()['id'] for n in range(1, 5)]
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [b1]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    status = next(e['id'] for e in admin.get('/api/catalogs/candidate-status').get_json()['entries']
                  if e['code'] == 'LANGUAGE_COURSE')
    budi = trainee('Budi', status_id=status, current_level_id=b1, program_id=pid)
    sari, dewi, eko = trainee('Sari'), trainee('Dewi'), trainee('Eko')
    trainee('Alt', archived_at=today())                                       # archiviert: zaehlt nirgends
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'instructor_id': ids['maria'],
                                          'module_id': mods[1], 'status': 'RUNNING'}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1, 'instructor_id': ids['tom'],
                                          'module_id': mods[3]}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi, sari]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})
    past = (today() - timedelta(days=3)).isoformat()
    s1 = admin.post('/api/sessions', json={'course_id': k1, 'date': past, 'start': '09:00',
                                           'end': '10:00'}).get_json()['sessions'][0]['id']
    admin.put(f'/api/sessions/{s1}/attendance', json={'entries': [{'trainee_id': budi, 'status': 'PRESENT'},
                                                                  {'trainee_id': sari, 'status': 'ABSENT'}]})
    s2 = admin.post('/api/sessions', json={'course_id': k2, 'date': past, 'start': '11:00',
                                           'end': '12:00'}).get_json()['sessions'][0]['id']
    tpl = admin.post('/api/assessment-templates', json={'name': 'T', 'passing_percent': 60, 'categories': [
        {'name': 'Sprechen', 'max_score': 10, 'weight': 1}]}).get_json()

    def assess(tid, points, final=True, days_ago=3, instructor='maria'):
        aid = admin.post('/api/assessments', json={
            'trainee_id': tid, 'template_id': tpl['id'], 'instructor_id': ids[instructor],
            'assessed_on': (today() - timedelta(days=days_ago)).isoformat(),
            'scores': [{'category_id': tpl['categories'][0]['id'], 'points': points}]}).get_json()['assessment']['id']
        if final:
            admin.post(f'/api/assessments/{aid}/finalize')
    assess(budi, 5, days_ago=10)       # aeltere zaehlt NICHT, nur die neueste
    assess(budi, 9)
    assess(dewi, 6, instructor='tom')
    assess(sari, 1, final=False)       # Entwurf
    return {'admin': admin, 'maria': as_user('maria'), 'tom': as_user('tom'), 'names': {budi: 'Budi', sari: 'Sari'},
            's2': s2}


def test_kennzahlen_fuer_alle(dash):
    body = dash['admin'].get('/api/dashboard').get_json()
    k = body['kpis']
    assert body['scope'] == 'all'
    assert (k['candidates'], k['active_candidates']) == (4, 2)            # Alt archiviert; Budi+Sari laufender Kurs
    assert (k['avg_assessment'], k['assessed_candidates']) == (75.0, 2)   # (90 + 60) / 2
    assert k['attendance']['rate'] == 0.5 and k['open_assessments'] == 1
    # Budi + Sari: je 1 von 4 abgeschlossen, Dewi: 3 von 4 -> 5 / 12
    assert k['modules'] == {'completed': 5, 'total': 12} and k['modules_completed'] == 41.7
    assert {r['label']: r['count'] for r in body['by_status']} == {'Im Sprachkurs': 1, None: 3}
    a = body['attention']
    assert a['open_assessments']['count'] == 1
    assert a['open_attendance']['count'] == 1 and a['open_attendance']['items'][0]['id'] == dash['s2']
    assert [p['name'] for p in a['low_attendance']['items']] == ['Sari']
    assert [p['name'] for p in a['without_course']['items']] == ['Eko']
    assert {p['name']: p['missing'] for p in a['incomplete_profile']['items']}['Sari'] == [
        'status', 'current_level', 'program']


def test_dozent_nur_eigene_kurse(dash):
    body = dash['maria'].get('/api/dashboard').get_json()
    k = body['kpis']
    assert body['scope'] == 'own_courses'
    assert (k['candidates'], k['active_candidates'], k['avg_assessment']) == (2, 2, 90.0)
    assert k['modules'] == {'completed': 2, 'total': 8}
    a = body['attention']
    assert a['open_attendance']['count'] == 0                             # Toms Termin ist nicht ihrer
    assert set(a) == {'open_assessments', 'open_attendance', 'low_attendance',     # kein Kurs-/Stammdaten-Recht
                      'open_lesson_ratings', 'lesson_coaching'}
    text = str(body)
    assert 'Dewi' not in text and 'Eko' not in text
    tom = dash['tom'].get('/api/dashboard').get_json()
    assert tom['kpis']['candidates'] == 1 and tom['attention']['open_attendance']['count'] == 1


@pytest.mark.parametrize('role,attention', [
    ('HR', {'low_attendance', 'incomplete_profile', 'lesson_coaching'}),
    ('MANAGEMENT', {'low_attendance', 'lesson_coaching'}),
    ('ACADEMIC_MANAGER', {'open_assessments', 'open_attendance', 'low_attendance', 'without_course',
                          'incomplete_profile', 'open_lesson_ratings', 'lesson_coaching'}),
])
def test_handlungsbedarf_nur_mit_recht(dash, as_user, grant, role, attention):
    grant('person', role)
    body = as_user('person').get('/api/dashboard').get_json()
    assert body['kpis']['candidates'] == 4 and set(body['attention']) == attention


def test_kandidat_und_ohne_rolle_kein_zugriff(dash, as_user, trainee):
    trainee('Kandidatin', msh_user='kandidatin')
    assert as_user('kandidatin').get('/api/dashboard').status_code == 403
    assert as_user('niemand').get('/api/dashboard').status_code == 403


def test_leere_daten_ohne_fehler(as_user):
    body = as_user('root_admin').get('/api/dashboard').get_json()
    assert body['kpis']['candidates'] == 0 and body['kpis']['avg_assessment'] is None
    assert body['kpis']['attendance'] is None and body['kpis']['modules_completed'] is None


def test_team_startseite(dash, as_user, grant):
    grant('hr', 'HR')
    res = as_user('hr').get('/', headers={'Accept': 'text/html'})
    assert res.status_code == 302 and res.headers['Location'].endswith('/dashboard')

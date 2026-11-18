"""Leistung: Uebersichten und Berichte stellen eine FESTE Zahl an Abfragen, egal wie viele Kandidaten,
Kurse, Termine und Bewertungen es gibt (kein N+1). Dazu Bewertungsliste seitenweise, Cache fuer CSS/JS.

Gemessen wird die Anzahl der SQL-Abfragen je Request — einmal mit wenig, einmal mit mehr Daten.
"""
from datetime import timedelta

import pytest
from sqlalchemy import event

from app.models.training_report import TrainingReport
from app.services.local_time import today


@pytest.fixture
def world(as_user, grant, trainee, db):
    """Ein Curriculum, zwei Dozenten, eine Vorlage; `grow(n)` legt einen Kurs mit n Kandidaten an —
    mit vergangenem Termin, erfasster Anwesenheit und Modul-Bewertung, je einer abgeschlossenen Bewertung, einer
    Abteilung (jede zweite von „galih" geleitet, sonst ist er SPV jedes zweiten), Report und interner Bewertung."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    admin.post('/api/programs', json={'name': 'Sprechkurs'})
    pid = admin.get('/api/programs').get_json()['programs'][0]['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    mods = [admin.post(f'/api/curricula/{cur}/modules', json={'name': f'M{n}'}).get_json()['id'] for n in range(4)]
    teachers = []
    for name in ('maria', 'tom'):
        teachers.append(admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                             'level_ids': [b1]}).get_json()['id'])
        grant(name, 'INSTRUCTOR')
    tpl = admin.post('/api/assessment-templates', json={'name': 'T', 'passing_percent': 60, 'categories': [
        {'name': 'Sprechen', 'max_score': 10, 'weight': 1, 'skill': 'SPEAKING'},
        {'name': 'Lesen', 'max_score': 10, 'weight': 1, 'skill': 'READING'}]}).get_json()
    count = [0]

    def grow(n):
        k = count[0]
        count[0] += 1
        teacher = teachers[k % 2]
        course = admin.post('/api/courses', json={'name': f'Kurs {k}', 'level_id': b1, 'instructor_id': teacher,
                                                  'module_id': mods[k % 4], 'status': 'RUNNING'}).get_json()['id']
        ids = [trainee(f'K{k}-{i}', current_level_id=b1, program_id=pid) for i in range(n)]
        admin.post(f'/api/courses/{course}/participants', json={'trainee_ids': ids})
        day = (today() - timedelta(days=2)).isoformat()
        session = admin.post('/api/sessions', json={'course_id': course, 'date': day, 'start': f'{8 + k:02d}:00',
                                                    'end': f'{8 + k:02d}:45', 'module_id': mods[k % 4]}
                             ).get_json()['sessions'][0]['id']
        admin.put(f'/api/sessions/{session}/attendance',
                  json={'entries': [{'trainee_id': t, 'status': 'PRESENT' if i % 2 else 'ABSENT'}
                                    for i, t in enumerate(ids)]})
        for i, t in enumerate(ids):
            aid = admin.post('/api/assessments', json={
                'trainee_id': t, 'template_id': tpl['id'], 'instructor_id': teacher, 'course_id': course,
                'assessed_on': day, 'scores': [{'category_id': c['id'], 'points': 5 + i % 5}
                                               for c in tpl['categories']]}).get_json()['assessment']['id']
            admin.post(f'/api/assessments/{aid}/finalize')
        stars = {a: 2 for a in 'vrwfp'}
        assert admin.put(f'/api/sessions/{session}/lesson-ratings', json={'homework_none': True, 'entries': [
            {'trainee_id': t, 'attendance': 'ABSENT'} if i % 2 == 0 else
            {'trainee_id': t, 'attendance': 'PRESENT', **stars, 'pu': 1, 'mi': 2, 'strength': 'V', 'target': 'R'}
            for i, t in enumerate(ids)]}).status_code == 200
        dept = admin.post('/api/departments', json={'name': f'Abt {k}', 'leaders': ['galih'] if k % 2 == 0 else []}
                          ).get_json()['id']
        for i, t in enumerate(ids):
            admin.patch(f'/api/candidates/{t}', json={'department_id': dept, 'supervisor': 'galih' if i % 2 else None})
            admin.post('/api/ratings', json={'trainee_id': t, 'r_practical': 7, 'r_reliability': 8, 'r_motivation': 9})
            db.session.add(TrainingReport(trainee_id=t, period=day, hours=6, learned='Montage geübt'))
        db.session.commit()
    return {'grow': grow, 'admin': admin}


def _queries(app, db, client, url):
    count = [0]

    def counter(*_):
        count[0] += 1
    event.listen(db.engine, 'before_cursor_execute', counter)
    try:
        response = client.get(url)
    finally:
        event.remove(db.engine, 'before_cursor_execute', counter)
    assert response.status_code == 200, (url, response.get_json())
    return count[0]


PAGES = [('root_admin', '/api/dashboard'), ('maria', '/api/dashboard'), ('maria', '/api/my-teaching'),
         ('root_admin', '/api/reports/attendance'), ('root_admin', '/api/reports/academic'),
         ('root_admin', '/api/reports/instructors'), ('root_admin', '/api/assessments'),
         ('root_admin', '/api/trainees'), ('root_admin', '/api/overall'), ('root_admin', '/api/candidates'),
         ('root_admin', '/api/rating-board'), ('galih', '/api/rating-board'), ('galih', '/api/overall'),
         ('root_admin', '/api/departments'), ('root_admin', '/api/overall/months')]


def test_abfragen_wachsen_nicht_mit_den_daten(app, db, as_user, world):
    world['grow'](2)
    world['grow'](2)
    few = {(user, url): _queries(app, db, as_user(user), url) for user, url in PAGES}
    for _ in range(3):
        world['grow'](4)
    many = {(user, url): _queries(app, db, as_user(user), url) for user, url in PAGES}
    grown = {key: (few[key], many[key]) for key in few if many[key] > few[key]}
    assert grown == {}, f'Abfragen wachsen mit den Daten (N+1): {grown}'


def test_bewertungen_seitenweise(world):
    world['grow'](3)
    world['grow'](3)
    admin = world['admin']
    first = admin.get('/api/assessments?per_page=4').get_json()
    second = admin.get('/api/assessments?per_page=4&page=2').get_json()
    assert (first['total'], first['page'], first['per_page'], len(first['assessments'])) == (6, 1, 4, 4)
    assert (second['page'], len(second['assessments'])) == (2, 2)
    assert not {a['id'] for a in first['assessments']} & {a['id'] for a in second['assessments']}
    assert admin.get('/api/assessments').get_json()['per_page'] == 50
    assert admin.get('/api/assessments?per_page=500').status_code == 400
    assert admin.get('/api/assessments?page=0').status_code == 400


def test_css_und_js_mit_version_bleiben_im_cache(app, as_user):
    client = app.test_client()
    version, original = 'abc123def456', app.config['ASSET_VERSION']
    app.config['ASSET_VERSION'] = version
    try:
        cached = client.get(f'/static/js/core.js?v={version}')
        other = client.get('/static/js/core.js?v=alt')
        plain = client.get('/static/js/core.js')
    finally:
        app.config['ASSET_VERSION'] = original
    assert cached.headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    assert 'immutable' not in other.headers.get('Cache-Control', '')
    assert 'immutable' not in plain.headers.get('Cache-Control', '')
    app.config['ASSET_VERSION'] = 'lokal'                       # lokal ohne GIT_COMMIT: nie festhalten
    try:
        local = client.get('/static/js/core.js?v=lokal')
    finally:
        app.config['ASSET_VERSION'] = original
    assert 'immutable' not in local.headers.get('Cache-Control', '')
    for r in (cached, other, plain, local):
        r.close()

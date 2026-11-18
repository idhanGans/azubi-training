"""Scope: instructors only see courses and candidates of their OWN courses."""
import pytest


@pytest.fixture
def world(as_user, grant, trainee):
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    ids = {}
    for name, login in (('Maria', 'maria'), ('Tom', 'tom')):
        ids[login] = admin.post('/api/instructors', json={'name': name, 'msh_user': login,
                                                          'level_ids': [b1]}).get_json()['id']
        grant(login, 'INSTRUCTOR')
    own, other = trainee('Budi', msh_user='budi'), trainee('Sari', msh_user='sari')
    c_own = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1,
                                             'instructor_id': ids['maria']}).get_json()['id']
    c_other = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1,
                                               'instructor_id': ids['tom']}).get_json()['id']
    admin.post(f'/api/courses/{c_own}/participants', json={'trainee_ids': [own]})
    admin.post(f'/api/courses/{c_other}/participants', json={'trainee_ids': [other]})
    return {'admin': admin, 'own': own, 'other': other, 'c_own': c_own, 'c_other': c_other,
            'maria': as_user('maria')}


def test_dozent_sieht_nur_eigene_kandidaten(world):
    maria = world['maria']
    assert [c['name'] for c in maria.get('/api/candidates').get_json()['items']] == ['Budi']
    assert [t['name'] for t in maria.get('/api/trainees').get_json()['trainees']] == ['Budi']
    assert maria.get(f'/api/candidates/{world["own"]}').status_code == 200
    assert maria.get(f'/api/candidates/{world["other"]}').status_code == 404


def test_dozent_sieht_nur_eigene_kurse(world):
    maria = world['maria']
    assert [c['name'] for c in maria.get('/api/courses').get_json()['courses']] == ['Kurs Maria']
    assert maria.get(f'/api/courses/{world["c_other"]}').status_code == 404


def test_reports_und_bewertungen_nur_eigene(world, as_user):
    for login in ('budi', 'sari'):
        assert as_user(login).post('/api/training/me', json={'period': '2026-09-22', 'hours': 6,
                                                             'lang': True}).status_code == 201
    maria = world['maria']
    assert maria.get(f'/api/training?trainee_id={world["other"]}').get_json()['reports'] == []
    assert {r['trainee_id'] for r in maria.get('/api/training').get_json()['reports']} == {world['own']}
    # rating only with assignment (SPV/leader) — an instructor without assignment rates nobody
    assert maria.post('/api/ratings', json={'trainee_id': world['own'], 'r_practical': 8, 'r_reliability': 7, 'r_motivation': 9}).status_code == 400
    for tid in (world['own'], world['other']):          # internal team rates all active ones
        assert world['admin'].post('/api/ratings', json={'trainee_id': tid, 'r_practical': 8, 'r_reliability': 7, 'r_motivation': 9}).status_code == 201
    # instructors only READ the individual ratings for their own courses
    ratings = maria.get('/api/ratings').get_json()['ratings']
    assert {r['trainee_id'] for r in ratings} == {world['own']}


def test_archivierter_kurs_zaehlt_nicht(world):
    world['admin'].post(f'/api/courses/{world["c_own"]}/archive')
    assert world['maria'].get('/api/candidates').get_json()['items'] == []


def test_dozenten_rolle_ohne_datensatz_sieht_nichts(as_user, grant, trainee):
    trainee('Budi')
    grant('ohne', 'INSTRUCTOR')
    client = as_user('ohne')
    assert client.get('/api/candidates').get_json()['items'] == []
    assert client.get('/api/courses').get_json()['courses'] == []
    assert client.get('/api/my-teaching').status_code == 403


def test_team_sieht_alles(world, as_user, grant):
    grant('hr', 'HR')
    assert len(as_user('hr').get('/api/candidates').get_json()['items']) == 2
    assert len(as_user('hr').get('/api/courses').get_json()['courses']) == 2


def test_mein_unterricht(world):
    body = world['maria'].get('/api/my-teaching').get_json()
    assert body['instructor']['name'] == 'Maria'
    assert body['stats'] == {'course_count': 1, 'running_count': 0, 'participant_count': 1,
                             'today_count': 0, 'hours_month': 0.0, 'open_attendance_count': 0,
                             'open_lesson_count': 0, 'open_assessment_count': 0}
    assert [p['name'] for p in body['participants']] == ['Budi']
    assert body['participants'][0]['courses'] == [{'id': world['c_own'], 'name': 'Kurs Maria'}]


def test_seiten_fuer_dozenten(world):
    html = world['maria'].get('/', headers={'Accept': 'text/html'})
    assert html.status_code == 302 and html.headers['Location'].endswith('/teaching')
    page = world['maria'].get('/teaching', headers={'Accept': 'text/html'}).get_data(as_text=True)
    assert 'href="/courses"' in page and 'href="/instructors"' not in page


def test_archivierter_dozent_verliert_mein_unterricht(world):
    admin = world['admin']
    admin.patch(f'/api/courses/{world["c_own"]}', json={'status': 'COMPLETED'})
    maria_id = world['admin'].get('/api/instructors').get_json()['instructors'][0]['id']
    admin.post(f'/api/instructors/{maria_id}/archive')
    assert world['maria'].get('/api/my-teaching').status_code == 403

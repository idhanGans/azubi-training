"""Fortschritt: Fertigkeiten-Zuordnung, Fertigkeiten-Werte, Modul-Fortschritt, Anwesenheit je Woche, Reichweite."""
from datetime import timedelta

import pytest

from app.services.local_time import today

TEMPLATE = {'name': 'Fortschritt-Test', 'passing_percent': 60, 'categories': [
    {'name': 'Lesen', 'max_score': 20, 'weight': 1},
    {'name': 'Antwortformel', 'max_score': 20, 'weight': 1, 'skill': 'SPEAKING'},
    {'name': 'Aussprache', 'max_score': 10, 'weight': 1, 'skill': 'SPEAKING'},
    {'name': 'Pünktlichkeit', 'max_score': 10, 'weight': 1}]}


@pytest.fixture
def pg(as_user, grant, trainee):
    """Curriculum mit 5 Modulen; Kurs Maria (Budi, Modul 3) und Kurs Tom (Dewi); eine Vorlage."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    admin.post('/api/programs', json={'name': 'Sprechkurs'})
    pid = admin.get('/api/programs').get_json()['programs'][0]['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    mods = [admin.post(f'/api/curricula/{cur}/modules', json={'name': f'Modul {n}'}).get_json()['id'] for n in range(1, 6)]
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [b1]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    budi, dewi = trainee('Budi', msh_user='budi'), trainee('Dewi', msh_user='dewi')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'instructor_id': ids['maria'],
                                          'module_id': mods[2]}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1, 'instructor_id': ids['tom']}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})
    tpl = admin.post('/api/assessment-templates', json=TEMPLATE).get_json()
    return {'admin': admin, 'maria': as_user('maria'), 'tom': as_user('tom'), 'b1': b1, 'mods': mods,
            'budi': budi, 'dewi': dewi, 'k1': k1, 'k2': k2, 'tpl': tpl, 'ids': ids}


def _final(pg, trainee, points, days_ago, instructor='maria'):
    """points = Punkte je Kategorie in Vorlagen-Reihenfolge."""
    scores = [{'category_id': c['id'], 'points': p} for c, p in zip(pg['tpl']['categories'], points)]
    res = pg['admin'].post('/api/assessments', json={
        'trainee_id': pg[trainee], 'template_id': pg['tpl']['id'], 'instructor_id': pg['ids'][instructor],
        'assessed_on': (today() - timedelta(days=days_ago)).isoformat(), 'scores': scores})
    aid = res.get_json()['assessment']['id']
    assert pg['admin'].post(f'/api/assessments/{aid}/finalize').status_code == 200
    return aid


# ---------- Fertigkeiten-Zuordnung an der Vorlage ----------

def test_fertigkeit_aus_namen_vorgeschlagen_oder_ausdruecklich(pg):
    skills = {c['name']: c['skill'] for c in pg['tpl']['categories']}
    assert skills == {'Lesen': 'READING', 'Antwortformel': 'SPEAKING', 'Aussprache': 'SPEAKING', 'Pünktlichkeit': None}
    res = pg['admin'].post('/api/assessment-templates', json={
        'name': 'X', 'passing_percent': 60, 'categories': [{'name': 'Hören', 'max_score': 5, 'weight': 1, 'skill': None}]})
    assert res.get_json()['categories'][0]['skill'] is None
    res = pg['admin'].post('/api/assessment-templates', json={
        'name': 'Y', 'passing_percent': 60, 'categories': [{'name': 'A', 'max_score': 5, 'weight': 1, 'skill': 'SINGING'}]})
    assert res.status_code == 400 and 'Fertigkeit' in res.get_json()['error']


def test_fertigkeit_auch_bei_gesperrter_vorlage_aenderbar(pg):
    _final(pg, 'budi', [10, 10, 5, 5], 3)
    tid, cats = pg['tpl']['id'], pg['tpl']['categories']
    assert pg['admin'].patch(f'/api/assessment-templates/{tid}', json={'categories': []}).status_code == 409
    res = pg['admin'].patch(f'/api/assessment-templates/{tid}', json={'skills': {str(cats[3]['id']): 'VOCABULARY'}})
    assert res.status_code == 200 and res.get_json()['categories'][3]['skill'] == 'VOCABULARY'
    log = pg['admin'].get('/api/activity').get_json()['activity'][0]
    assert log['detail']['changes']['fertigkeiten'] == {'Pünktlichkeit': [None, 'Wortschatz']}
    other = pg['admin'].post('/api/assessment-templates', json={**TEMPLATE, 'name': 'Andere'}).get_json()
    res = pg['admin'].patch(f'/api/assessment-templates/{tid}', json={'skills': {str(other['categories'][0]['id']): 'READING'}})
    assert res.status_code == 400


# ---------- Fertigkeiten-Werte ----------

def test_fertigkeiten_summieren_kategorien_und_zeigen_neuesten_stand(pg):
    _final(pg, 'budi', [10, 12, 6, 10], 20)            # Lesen 50 %, Sprechen 18/30 = 60 %
    _final(pg, 'budi', [16, 15, 9, 0], 5)              # Lesen 80 %, Sprechen 24/30 = 80 %
    pg['admin'].post('/api/assessments', json={        # Entwurf zaehlt nicht
        'trainee_id': pg['budi'], 'template_id': pg['tpl']['id'], 'instructor_id': pg['ids']['maria'],
        'assessed_on': today().isoformat(), 'scores': [{'category_id': pg['tpl']['categories'][0]['id'], 'points': 1}]})
    body = pg['admin'].get(f'/api/candidates/{pg["budi"]}/progress').get_json()
    skills = {s['skill']: s for s in body['skills']}
    assert list(skills) == ['READING', 'SPEAKING']     # feste Reihenfolge, „Pünktlichkeit" ohne Fertigkeit fehlt
    assert (skills['READING']['current'], skills['READING']['first'], skills['READING']['change']) == (80.0, 50.0, 30.0)
    assert (skills['SPEAKING']['current'], skills['SPEAKING']['change'], skills['SPEAKING']['count']) == (80.0, 20.0, 2)
    assert [p['percent'] for p in skills['SPEAKING']['series']] == [60.0, 80.0]
    assert [t['overall_percent'] for t in body['assessment_trend']] == [67.5, 61.3]   # Gesamt inkl. Pünktlichkeit


# ---------- Module ----------

def test_module_vor_dem_aktuellen_sind_abgeschlossen(pg):
    m = pg['admin'].get(f'/api/candidates/{pg["budi"]}/progress').get_json()['modules']
    assert len(m) == 1
    assert (m[0]['completed'], m[0]['total'], m[0]['percent']) == (2, 5, 40.0)
    assert [i['state'] for i in m[0]['items']] == ['done', 'done', 'current', 'open', 'open']
    assert m[0]['current']['name'] == 'Modul 3'
    pg['admin'].patch(f'/api/modules/{pg["mods"][4]}', json={'status': 'ARCHIVED'})
    pg['admin'].patch(f'/api/courses/{pg["k1"]}', json={'status': 'COMPLETED'})
    m = pg['admin'].get(f'/api/candidates/{pg["budi"]}/progress').get_json()['modules'][0]
    assert (m['completed'], m['total'], m['current']) == (3, 4, None)


def test_weitester_kurs_je_curriculum_zaehlt(pg):
    k3 = pg['admin'].post('/api/courses', json={'name': 'Aufbaukurs', 'level_id': pg['b1'],
                                                'module_id': pg['mods'][3]}).get_json()['id']
    pg['admin'].post(f'/api/courses/{k3}/participants', json={'trainee_ids': [pg['budi']]})
    m = pg['admin'].get(f'/api/candidates/{pg["budi"]}/progress').get_json()['modules']
    assert len(m) == 1 and m[0]['course']['name'] == 'Aufbaukurs' and m[0]['completed'] == 3


# ---------- Anwesenheit je Woche ----------

def test_anwesenheit_je_woche_mit_derselben_quote(pg):
    admin = pg['admin']
    monday = today() - timedelta(days=today().weekday())
    days = [monday - timedelta(days=14), monday - timedelta(days=12), monday - timedelta(days=7)]
    for day, status in zip(days, ('PRESENT', 'ABSENT', 'EXCUSED')):
        sid = admin.post('/api/sessions', json={'course_id': pg['k1'], 'date': day.isoformat(), 'start': '10:00',
                                                'end': '11:00'}).get_json()['sessions'][0]['id']
        admin.put(f'/api/sessions/{sid}/attendance', json={'entries': [{'trainee_id': pg['budi'], 'status': status}]})
    weeks = admin.get(f'/api/candidates/{pg["budi"]}/progress').get_json()['attendance']['weeks']
    assert [(w['week_start'], w['present'], w['absent'], w['excused'], w['rate']) for w in weeks] == [
        (days[0].isoformat(), 1, 1, 0, 0.5), (days[2].isoformat(), 0, 0, 1, None)]


# ---------- Reichweite ----------

def test_reichweite_und_kandidat_selbst(pg, as_user, grant):
    _final(pg, 'dewi', [10, 10, 5, 5], 3, instructor='tom')
    assert pg['maria'].get(f'/api/candidates/{pg["dewi"]}/progress').status_code == 404
    assert pg['tom'].get(f'/api/candidates/{pg["dewi"]}/progress').get_json()['skills'][0]['current'] == 50.0
    # Maria sieht Budi — aber Module/Anwesenheit nur aus IHREN Kursen
    pg['admin'].post(f'/api/courses/{pg["k2"]}/participants', json={'trainee_ids': [pg['budi']]})
    pg['admin'].patch(f'/api/courses/{pg["k2"]}', json={'module_id': pg['mods'][4]})
    assert pg['maria'].get(f'/api/candidates/{pg["budi"]}/progress').get_json()['modules'][0]['completed'] == 2
    assert pg['admin'].get(f'/api/candidates/{pg["budi"]}/progress').get_json()['modules'][0]['completed'] == 4
    own = as_user('dewi').get('/api/my-progress').get_json()
    assert own['skills'][0]['current'] == 50.0 and own['modules'][0]['completed'] == 4
    assert as_user('budi').get('/api/my-progress').get_json()['skills'] == []
    assert as_user('budi').get(f'/api/candidates/{pg["dewi"]}/progress').status_code == 403
    grant('hr', 'HR')
    assert as_user('hr').get(f'/api/candidates/{pg["dewi"]}/progress').status_code == 200
    assert pg['maria'].get('/api/my-progress').status_code == 403


def test_vorbelegung_der_migration_passt_zu_den_fertigkeiten():
    from app.models.assessment_category import SKILLS
    from tests.conftest import _load_migration
    names = _load_migration('0010_category_skill.py').NAMES
    assert names == {label.lower(): code for code, label in SKILLS.items()}

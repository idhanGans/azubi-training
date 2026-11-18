"""Verlauf (Audit-Trail): vollstaendig, unveraenderlich, filterbar, nur fuer Super-Admins."""
import inspect
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.services.local_time import today

#: Schreibende Routen OHNE eigenen Verlaufs-Eintrag — jede mit Begruendung. Alles andere MUSS protokollieren.
EXEMPT = {
    'assessment_templates.evaluate': 'Vorschau-Berechnung, speichert nichts',
    'lesson_ratings.evaluate': 'Live-Vorschau der Modul-Bewertung, speichert nichts',
    'notifications.read_one': 'eigener Lesestatus, keine fachliche Aenderung',
    'notifications.read_all': 'eigener Lesestatus, keine fachliche Aenderung',
}


def test_jede_schreibende_route_protokolliert(app):
    missing = []
    for rule in app.url_map.iter_rules():
        if not rule.methods - {'GET', 'HEAD', 'OPTIONS'} or rule.endpoint in EXEMPT:
            continue
        source = inspect.getsource(app.view_functions[rule.endpoint])
        if not any(marker in source for marker in ('audit.log(', '_log(')):
            missing.append(f'{sorted(rule.methods - {"HEAD", "OPTIONS"})} {rule.rule}')
    assert not missing, f'ohne Verlaufs-Eintrag: {missing}'


def test_eintraege_sind_unveraenderlich(as_user, db):
    as_user('root_admin').post('/api/candidates', json={'name': 'Budi'})
    for sql in ("UPDATE activity_log SET summary = 'geaendert'", 'DELETE FROM activity_log'):
        with pytest.raises(DBAPIError, match='unveraenderlich'):
            db.session.execute(text(sql))
            db.session.flush()
        db.session.rollback()
    assert db.session.execute(text("SELECT summary FROM activity_log")).scalar().startswith('Kandidat angelegt')


@pytest.fixture
def log(as_user, grant, trainee):
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    admin.post('/api/instructors', json={'name': 'Anna Müller', 'msh_user': 'anna.mueller', 'level_ids': [b1]})
    grant('anna.mueller', 'ACADEMIC_MANAGER')
    anna = as_user('anna.mueller')
    budi = trainee('Max Mustermann')
    tpl = anna.post('/api/assessment-templates', json={'name': 'Monat', 'passing_percent': 60, 'categories': [
        {'name': 'Lesen', 'max_score': 100, 'weight': 1}]}).get_json()
    aid = anna.post('/api/assessments', json={'trainee_id': budi, 'template_id': tpl['id'], 'instructor_id': 1,
                                              'assessed_on': today().isoformat(),
                                              'scores': [{'category_id': tpl['categories'][0]['id'], 'points': 82}]}
                    ).get_json()['assessment']['id']
    anna.post(f'/api/assessments/{aid}/finalize')
    anna.patch(f'/api/assessments/{aid}', json={'scores': [{'category_id': tpl['categories'][0]['id'], 'points': 85}],
                                                'reason': 'Tippfehler'})
    admin.patch(f'/api/candidates/{budi}', json={'fach': 'Elektro'})
    anna.patch(f'/api/assessment-templates/{tpl["id"]}', json={'skills': {str(tpl['categories'][0]['id']): None}})
    return {'admin': admin, 'budi': budi}


def test_beispiel_aus_dem_auftrag(log):
    entry = next(a for a in log['admin'].get('/api/activity').get_json()['activity'] if a['action'] == 'assessment.correct')
    assert (entry['actor'], entry['actor_name'], entry['entity_type'], entry['entity_id'], entry['entity_name']) == (
        'anna.mueller', 'Anna Müller', 'trainee', log['budi'], 'Max Mustermann')
    assert {'field': 'Gesamt', 'old': 82.0, 'new': 85.0} in entry['changes']
    assert entry['reason'] == 'Tippfehler' and entry['created_at']


def test_verschachtelte_aenderungen_flach(log):
    entry = next(a for a in log['admin'].get('/api/activity').get_json()['activity']
                 if a['action'] == 'assessment_template.update')
    assert entry['changes'] == [{'field': 'fertigkeiten › Lesen', 'old': 'Lesen', 'new': None}]


def test_filter_und_seiten(log):
    admin = log['admin']
    get = lambda q: admin.get(f'/api/activity?{q}').get_json()
    assert {a['actor'] for a in get('actor=anna.mueller')['activity']} == {'anna.mueller'}
    assert {a['action'] for a in get('action=assessment')['activity']} == {'assessment.create', 'assessment.finalize',
                                                                          'assessment.correct'}
    assert [a['action'] for a in get('action=assessment.correct')['activity']] == ['assessment.correct']
    person = get(f'entity_type=trainee&entity_id={log["budi"]}')['activity']
    assert {a['action'] for a in person} >= {'trainee.update', 'assessment.correct'}
    assert [a['action'] for a in get('q=tippfehler')['activity']] == ['assessment.correct']
    assert get(f'from={(today() + timedelta(days=1)).isoformat()}')['activity'] == []
    assert len(get(f'from={today().isoformat()}&to={today().isoformat()}')['activity']) >= 6
    first = get('limit=2')
    rest = get(f'limit=2&before_id={first["next_before_id"]}')
    assert len(first['activity']) == 2 and first['next_before_id'] == first['activity'][-1]['id']
    assert all(a['id'] < first['activity'][-1]['id'] for a in rest['activity'])
    facets = admin.get('/api/activity/facets').get_json()
    assert {'login': 'anna.mueller', 'name': 'Anna Müller'} in facets['actors']
    assert 'assessment.correct' in facets['actions']
    assert admin.get('/api/activity?limit=5000').status_code == 400


@pytest.mark.parametrize('role', ['HR', 'ACADEMIC_MANAGER', 'MANAGEMENT', 'INSTRUCTOR'])
def test_nur_super_admin(log, as_user, grant, trainee, role):
    grant('person', role)
    for path in ('/api/activity', '/api/activity/facets'):
        assert as_user('person').get(path).status_code == 403
    assert as_user('person').get('/activity', headers={'Accept': 'text/html'}).status_code == 403
    trainee('Kandidat', msh_user='kandidat')
    assert as_user('kandidat').get('/api/activity').status_code == 403


def test_langer_verlaufstext_wird_gekuerzt_nicht_500(as_user, trainee, db):
    """24 echte Namen auf einmal in einen Kurs: der Text passt nicht in `summary` (400) — gekuerzt mit „…",
    die vollstaendige Liste steht in `detail`, die Aufnahme klappt."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    course = admin.post('/api/courses', json={'name': 'Kurs A', 'level_id': b1}).get_json()['id']
    ids = [trainee(f'Dimas Rio Rahmat Wibowo {n:02d}') for n in range(24)]
    res = admin.post(f'/api/courses/{course}/participants', json={'trainee_ids': ids})
    assert res.status_code == 200 and len(res.get_json()['added']) == 24
    summary, detail = db.session.execute(text(
        "SELECT summary, detail FROM activity_log WHERE action = 'course.participants_add'")).one()
    assert len(summary) <= 400 and summary.endswith('…')
    assert len(detail['trainees']) == 24

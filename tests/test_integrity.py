"""Datenintegritaet: wer/wann steht an jeder geaenderten Zeile, Wertebereiche prueft auch die Datenbank,
und eine verletzte Datenbank-Regel (z.B. zwei legen gleichzeitig denselben Namen an) ist nie ein 500."""
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.services.local_time import today


@pytest.fixture
def busy(as_user, grant):
    """Moeglichst viele schreibende Wege einmal durchlaufen — alles ueber die API, als echte Logins."""
    admin = as_user('root_admin')
    grant('maria', 'INSTRUCTOR')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    status = admin.post('/api/catalogs/candidate-status', json={'code': 'PAUSE', 'name': 'Pausiert'}).get_json()['id']
    admin.patch(f'/api/catalogs/candidate-status/{status}', json={'name': 'Pausiert (Urlaub)'})
    pid = admin.post('/api/programs', json={'name': 'Sprechkurs'}).get_json()['id']
    admin.patch(f'/api/programs/{pid}', json={'description': 'B1 fuer Handwerk'})
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    mods = [admin.post(f'/api/curricula/{cur}/modules', json={'name': f'M{n}'}).get_json()['id'] for n in range(3)]
    admin.put(f'/api/curricula/{cur}/module-order', json={'module_ids': list(reversed(mods))})
    mats = [admin.post(f'/api/modules/{mods[0]}/materials', json={'type': 'LINK', 'title': f'L{n}',
                                                                  'url': f'https://example.org/{n}'}).get_json()['id']
            for n in range(2)]
    admin.put(f'/api/modules/{mods[0]}/material-order', json={'material_ids': list(reversed(mats))})
    admin.post(f'/api/materials/{mats[0]}/archive')
    maria = admin.post('/api/instructors', json={'name': 'Maria', 'msh_user': 'maria', 'level_ids': [b1]}).get_json()['id']
    admin.patch(f'/api/instructors/{maria}', json={'qualification': 'DaF'})
    cand = admin.post('/api/candidates', json={'name': 'Budi Santoso', 'msh_user': 'budi'}).get_json()['id']
    admin.patch(f'/api/candidates/{cand}', json={'phone': '+49 30 1'})
    course = admin.post('/api/courses', json={'name': 'Kurs A', 'level_id': b1, 'instructor_id': maria,
                                              'module_id': mods[1]}).get_json()['id']
    admin.patch(f'/api/courses/{course}', json={'status': 'RUNNING'})
    admin.post(f'/api/courses/{course}/participants', json={'trainee_ids': [cand]})
    past = (today() - timedelta(days=1)).isoformat()
    session = admin.post('/api/sessions', json={'course_id': course, 'date': past, 'start': '09:00',
                                                'end': '10:00'}).get_json()['sessions'][0]['id']
    admin.patch(f'/api/sessions/{session}', json={'room': 'Raum 2'})
    admin.put(f'/api/sessions/{session}/attendance', json={'entries': [{'trainee_id': cand, 'status': 'PRESENT'}]})
    admin.put(f'/api/sessions/{session}/attendance', json={'entries': [{'trainee_id': cand, 'status': 'ABSENT'}]})
    tpl = admin.post('/api/assessment-templates', json={'name': 'T', 'passing_percent': 60, 'categories': [
        {'name': 'Sprechen', 'max_score': 10, 'weight': 1}]}).get_json()
    admin.patch(f'/api/assessment-templates/{tpl["id"]}', json={'description': 'Neu'})
    score = lambda p: [{'category_id': tpl['categories'][0]['id'], 'points': p}]  # noqa: E731
    aid = admin.post('/api/assessments', json={'trainee_id': cand, 'template_id': tpl['id'], 'instructor_id': maria,
                                               'assessed_on': past, 'scores': score(5)}).get_json()['assessment']['id']
    admin.post(f'/api/assessments/{aid}/finalize')
    budi = as_user('budi')
    rid = budi.post('/api/training/me', json={'period': past, 'hours': 6, 'lang': True}).get_json()['id']
    budi.put(f'/api/training/me/{rid}', json={'period': past, 'hours': 7, 'lang': True})
    return {'admin': admin, 'status': status, 'mods': mods, 'mats': mats, 'aid': aid, 'rid': rid}


def _columns(db, name):
    return {table for (table,) in db.session.execute(text(
        "SELECT table_name FROM information_schema.columns WHERE table_schema = 'public' AND column_name = :c"),
        {'c': name})}


def test_jede_geaenderte_zeile_nennt_wer_und_wann(db, busy):
    """Ueber alle Tabellen: wo `updated_at` steht, steht auch `updated_by` (und umgekehrt); was ueber die
    API angelegt wurde, traegt `created_by`. Deckt auch Wege ab, die es in einer Route vergessen haetten."""
    missing = {}
    for table in _columns(db, 'updated_at') & _columns(db, 'updated_by'):
        bad = db.session.execute(text(f'SELECT count(*) FROM {table} WHERE (updated_at IS NULL) <> (updated_by IS NULL)')).scalar()
        if bad:
            missing[f'{table}.updated_*'] = bad
    for table in _columns(db, 'created_by'):
        bad = db.session.execute(text(f"SELECT count(*) FROM {table} WHERE created_by IS NULL")).scalar()
        seeded = table in ('candidate_status', 'language_level')         # Startwerte aus der Migration
        if bad and not seeded:
            missing[f'{table}.created_by'] = bad
    assert missing == {}


def test_bisher_fehlende_wer_angaben(db, busy):
    q = lambda sql, **p: db.session.execute(text(sql), p).one()  # noqa: E731
    assert q('SELECT status, updated_by FROM assessment WHERE id = :i', i=busy['aid']) == ('FINAL', 'root_admin')
    moved = {busy['mods'][0], busy['mods'][2]}                  # umgekehrt: die mittlere bleibt, wo sie ist
    assert {i: by for i, by in db.session.execute(text('SELECT id, updated_by FROM course_module'))} == {
        i: ('root_admin' if i in moved else None) for i in busy['mods']}
    assert q('SELECT updated_by FROM material WHERE id = :i', i=busy['mats'][1]) == ('root_admin',)
    name, created_by, updated_by, updated_at = q('SELECT name, created_by, updated_by, updated_at FROM candidate_status '
                                                 'WHERE id = :i', i=busy['status'])
    assert (name, created_by, updated_by) == ('Pausiert (Urlaub)', 'root_admin', 'root_admin') and updated_at
    hours, updated = q('SELECT hours, updated_at FROM training_report WHERE id = :i', i=busy['rid'])
    assert hours == 7 and updated is not None
    entry = busy['admin'].get('/api/catalogs/candidate-status').get_json()['entries']
    assert next(e for e in entry if e['id'] == busy['status'])['updated_by'] == 'root_admin'


@pytest.mark.parametrize('sql', [
    'UPDATE training_report SET hours = 25',
    'UPDATE training_report SET hours = -1',
    'UPDATE leiter_rating SET r_language = 11',
    'UPDATE leiter_rating SET r_attitude = 0',
    'UPDATE assessment_score SET points = 2.3',
])
def test_wertebereiche_prueft_auch_die_datenbank(db, busy, sql):
    """Stunden 0..24, Leiter-Bewertung 1..10, Punkte in 0,5er-Schritten — auch an der Anwendung vorbei."""
    db.session.execute(text("INSERT INTO leiter_rating (trainee_id, r_language, r_attitude, created_at) "
                            "SELECT id, 5, 5, now() FROM trainee LIMIT 1"))
    db.session.execute(text("SET LOCAL azubi.assessment_correction = 'on'"))   # Sperre (0015) aus: hier zaehlt CHECK
    with pytest.raises(IntegrityError):
        db.session.execute(text(sql))
        db.session.flush()
    db.session.rollback()


def test_verletzte_db_regel_ist_409_statt_500(as_user, db, monkeypatch):
    """Die Vorab-Pruefung auf doppelte Namen laeuft an der Datenbank vorbei, wenn zwei gleichzeitig anlegen —
    nachgestellt, indem sie hier ausfaellt: die UNIQUE-Regel greift, Antwort 409, nichts gespeichert."""
    from app.routes import curriculum as route
    admin = as_user('root_admin')
    assert admin.post('/api/programs', json={'name': 'Sprechkurs'}).status_code == 201
    monkeypatch.setattr(route.svc, 'read_program', lambda data, program=None: {'name': data['name']})
    res = admin.post('/api/programs', json={'name': 'Sprechkurs'})
    assert res.status_code == 409 and res.get_json()['code'] == 'DB_RULE'
    assert 'gleichzeitig' in res.get_json()['error']
    assert len(admin.get('/api/programs').get_json()['programs']) == 1
    assert db.session.execute(text("SELECT count(*) FROM activity_log WHERE action = 'program.create'")).scalar() == 1

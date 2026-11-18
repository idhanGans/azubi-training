"""mask.sql (masked copy of the production DB for release/user sandboxes): must run on main's (0002)
schema AND on head, leave behind no real names/logins/contact data, keep daily reports,
and turn the activity log's protection trigger back on."""
import json
import os

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text

from tests.test_migrations import _migrate

MASK = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mask.sql'),
            encoding='utf-8').read()
NAMES = ['Mulya Irawan', 'Siti Rahma', 'Siti', 'Anton Ru‘sdi']


def _run_mask(db):
    db.session.commit()
    raw = db.session.connection().connection
    with raw.cursor() as cur:         # DBAPI directly: no parameter parsing (%, :) in PL/pgSQL
        cur.execute(MASK)
    raw.commit()


def _leftovers(db):
    """All texts that could contain real names, logins or contact data."""
    rows = db.session.execute(text(
        "SELECT coalesce(summary,'') || ' ' || coalesce(entity_name,'') || ' ' || coalesce(detail::text,'') || ' ' "
        "|| coalesce(actor,'') FROM activity_log")).scalars().all()
    blob = ' '.join(rows) + ' ' + ' '.join(db.session.execute(text(
        "SELECT coalesce(name,'') || ' ' || coalesce(nickname,'') || ' ' || coalesce(email,'') || ' ' "
        "|| coalesce(msh_user,'') FROM trainee")).scalars().all())
    return [n for n in NAMES + ['mulya_irawan', 'mulya@example.org']
            if n in blob or json.dumps(n)[1:-1] in blob]


def test_mask_auf_main_schema_0002(app, db):
    _migrate(downgrade, revision='0002')
    try:
        db.session.execute(text(
            "INSERT INTO trainee (id, name, nickname, email, fach, msh_user, active, created_at) VALUES "
            "(1, 'Mulya Irawan', 'Mulya', 'mulya@example.org', 'SHK', 'mulya_irawan', true, now()),"
            "(2, 'Siti Rahma', NULL, NULL, 'Elektro', 'siti', true, now()),"
            "(3, 'Siti', NULL, NULL, 'SHK', NULL, true, now())"))
        db.session.execute(text(
            "INSERT INTO training_report (trainee_id, period, hours, lang, tech, learned, station, created_at) "
            "VALUES (1, '2026-09-18', 6, true, false, 'Konjunktiv II geübt', 'Wärmepumpe', now())"))
        db.session.execute(text(
            "INSERT INTO leiter_rating (trainee_id, rater, r_language, note, created_at) "
            "VALUES (1, 'anna_hr', 7, 'Mulya ist engagiert', now())"))
        db.session.execute(text(
            "INSERT INTO activity_log (actor, action, entity_type, entity_id, entity_name, summary, detail, created_at) "
            "VALUES ('root', 'trainee.create', 'trainee', 2, 'Siti Rahma', 'Teilnehmer angelegt: Siti Rahma', "
            "'{\"name\": \"Siti Rahma\"}', now()),"
            "('mulya_irawan', 'report.create', 'trainee', 1, 'Mulya Irawan', 'Report 2026-09-18', NULL, now())"))
        _run_mask(db)
        assert _leftovers(db) == []
        assert db.session.execute(text('SELECT name FROM trainee ORDER BY id')).scalars().all() == [
            'Kandidat 001', 'Kandidat 002', 'Kandidat 003']
        assert db.session.execute(text("SELECT summary FROM activity_log WHERE action = 'trainee.create'")).scalar() \
            == 'Teilnehmer angelegt: Kandidat 002'                         # not "Kandidat 003 Rahma"
        report = db.session.execute(text('SELECT period, hours, learned, station FROM training_report')).one()
        assert tuple(report) == ('2026-09-18', 6, 'Konjunktiv II geübt', 'Wärmepumpe')
        assert db.session.execute(text('SELECT note FROM leiter_rating')).scalar() is None
    finally:
        db.session.rollback()
        db.session.execute(text('TRUNCATE trainee, training_report, leiter_rating, activity_log RESTART IDENTITY CASCADE'))
        _migrate(upgrade)


def test_mask_auf_head_mit_verlauf_aus_der_app(as_user, grant, db):
    """Names end up in the activity log via the app (also in JSON with \\u escapes) — all get replaced."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    ids = [admin.post('/api/candidates', json={'name': n, 'msh_user': login, 'email': f'{login}@example.org'})
           .get_json()['id'] for n, login in (('Mulya Irawan', 'mulya_irawan'), ('Anton Ru‘sdi', 'anton'))]
    pid = admin.post('/api/programs', json={'name': 'Deutsch'}).get_json()['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    module = admin.post(f'/api/curricula/{cur}/modules', json={'name': 'Modul 1'}).get_json()['id']
    course = admin.post('/api/courses', json={'name': 'Kurs A', 'level_id': b1, 'module_id': module}).get_json()['id']
    admin.post(f'/api/courses/{course}/participants', json={'trainee_ids': ids})
    session = admin.post('/api/sessions', json={'course_id': course, 'date': '2026-09-01', 'start': '09:00',
                                                'end': '10:00'}).get_json()['sessions'][0]['id']
    admin.put(f'/api/sessions/{session}/attendance',
              json={'entries': [{'trainee_id': t, 'status': 'PRESENT'} for t in ids]})
    as_user('mulya_irawan').post('/api/training/me', json={'period': '2026-09-02', 'hours': 5, 'learned': 'Übergabe'})
    stars = {'v': 2, 'r': 2, 'w': 3, 'f': 2, 'p': 1, 'pu': 1, 'mi': 1, 'ha': 2, 'strength': 'W', 'target': 'P'}
    res = admin.put(f'/api/sessions/{session}/lesson-ratings', json={'entries': [
        {'trainee_id': ids[0], 'attendance': 'PRESENT', **stars, 'note': 'Mulya Irawan braucht Hilfe'},
        {'trainee_id': ids[1], 'attendance': 'ABSENT', 'note': 'krank'}]})
    assert res.status_code == 200, res.get_json()
    admin.post('/api/ratings', json={'trainee_id': ids[0], 'r_practical': 6, 'r_reliability': 7, 'r_motivation': 8,
                                     'note': 'Mulya Irawan kommt oft zu spät'})
    assert any('\\u2018' in d for d in db.session.execute(text(
        'SELECT detail::text FROM activity_log WHERE detail IS NOT NULL')).scalars())   # precondition of the test

    _run_mask(db)
    assert _leftovers(db) == []
    assert db.session.execute(text('SELECT learned FROM training_report')).scalar() == 'Übergabe'
    assert db.session.execute(text('SELECT note, w, p FROM lesson_rating')).one() == (None, 3, 1)  # stars remain
    assert db.session.execute(text('SELECT note, r_motivation FROM staff_rating')).one() == (None, 8)
    with pytest.raises(Exception, match='unveraenderlich'):                     # protection trigger back on
        db.session.execute(text("UPDATE activity_log SET summary = 'x'"))
    db.session.rollback()

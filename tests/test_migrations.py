"""Migrations: each reversible, models == schema, existing data from today's main (0002) survives up to head.
Plus 0003/0004 in detail: no timestamp shifts, candidate numbers in id order."""
from datetime import datetime, timezone

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text


def _migrate(step, **kw):
    """Alembic runs on its OWN connection — the test session must
    end its transaction first, otherwise ALTER TABLE waits on its locks."""
    from app.extensions import db
    db.session.commit()
    step(**kw)


def test_0003_uebernimmt_bestandsdaten_und_ist_umkehrbar(app, db):
    _migrate(downgrade, revision='0002')
    db.session.execute(text(
        "INSERT INTO trainee (id, name, msh_user, active, created_at) "
        "VALUES (1, 'Alt', 'alt_login', true, '2026-09-16 08:30:00')"))
    db.session.execute(text(
        "INSERT INTO activity_log (actor, action, created_at) VALUES ('x', 'trainee.create', '2026-09-16 08:30:00')"))
    _migrate(upgrade)
    row = db.session.execute(text('SELECT created_at, archived_at FROM trainee WHERE id = 1')).one()
    assert row.created_at == datetime(2026, 9, 16, 8, 30, tzinfo=timezone.utc)
    assert row.archived_at is None
    assert db.session.execute(text("SELECT count(*) FROM user_role")).scalar() == 0

    _migrate(downgrade, revision='0002')
    naive = db.session.execute(text('SELECT created_at FROM trainee WHERE id = 1')).scalar()
    assert naive == datetime(2026, 9, 16, 8, 30)
    _migrate(upgrade)


def test_0004_nummeriert_bestand_in_id_reihenfolge(app, db):
    _migrate(downgrade, revision='0003')
    for tid, name in ((5, 'Fuenf'), (2, 'Zwei'), (9, 'Neun')):
        db.session.execute(text("INSERT INTO trainee (id, name, active, created_at) "
                                "VALUES (:i, :n, true, now())"), {'i': tid, 'n': name})
    _migrate(upgrade)
    rows = db.session.execute(text('SELECT id, candidate_no FROM trainee ORDER BY id')).all()
    assert [tuple(r) for r in rows] == [(2, 'K-00001'), (5, 'K-00002'), (9, 'K-00003')]
    nxt = db.session.execute(text("INSERT INTO trainee (name, active, created_at) VALUES ('Neu', true, now()) "
                                  "RETURNING candidate_no")).scalar()
    assert nxt == 'K-00004'
    _migrate(downgrade, revision='0003')
    _migrate(upgrade)


def _revisions():
    """All revisions from the first to head (order per Alembic, not per filename)."""
    from alembic.script import ScriptDirectory
    from flask import current_app
    config = current_app.extensions['migrate'].migrate.get_config()
    return [r.revision for r in reversed(list(ScriptDirectory.from_config(config).walk_revisions()))]


def test_jede_migration_hin_und_zurueck(app, db):
    """Empty DB -> head, then every single step back and forward again (downgrade complete, no remainder)."""
    _migrate(downgrade, revision='base')
    tables = db.session.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' "
                                     "AND table_name <> 'alembic_version'")).scalar()
    assert tables == 0, 'Downgrade bis base laesst Tabellen zurueck'
    _migrate(upgrade)
    revisions = _revisions()
    assert revisions[0] == '0001' and len(revisions) >= 12
    for previous, current in reversed(list(zip(['base'] + revisions, revisions))):
        _migrate(downgrade, revision=previous)
        _migrate(upgrade, revision=current)
    _migrate(upgrade)


def test_modelle_entsprechen_den_migrationen(app, db):
    """No difference between SQLAlchemy models and the migrated schema — otherwise a
    `flask db migrate` would e.g. delete indexes that only exist in a migration."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    db.session.commit()
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={'compare_type': True}), db.metadata)
    assert diff == []


def test_bestand_aus_main_0002_kommt_heil_bis_head(app, db, as_user):
    """The next main deploy migrates real data from 0002 to head: nothing gets lost,
    timestamps stay, logins become candidates, and the new areas work with the existing data."""
    _migrate(downgrade, revision='0002')
    db.session.execute(text(
        "INSERT INTO trainee (id, name, nickname, email, fach, abteilung, msh_user, active, created_at) VALUES "
        "(7, 'Budi Santoso', 'Budi', 'budi@example.org', 'Elektro', 'Berlin', 'budi', true, '2026-09-01 07:00:00'),"
        "(3, 'Siti Rahma', NULL, NULL, 'SHK', NULL, NULL, false, '2026-09-02 07:00:00')"))
    db.session.execute(text(
        "INSERT INTO training_report (trainee_id, period, hours, lang, tech, learned, station, created_at) VALUES "
        "(7, '2026-09-10', 6.5, true, false, 'Konjunktiv II', 'Wärmepumpe', '2026-09-10 16:00:00')"))
    db.session.execute(text(
        "INSERT INTO leiter_rating (trainee_id, rater, r_language, r_technical, r_attitude, note, created_at) VALUES "
        "(7, 'anna_hr', 8, 7, 9, 'gut', '2026-09-11 09:00:00')"))
    db.session.execute(text(
        "INSERT INTO activity_log (actor, action, summary, created_at) VALUES "
        "('anna_hr', 'rating.create', 'Bewertung Budi', '2026-09-11 09:00:00')"))
    _migrate(upgrade)

    rows = db.session.execute(text('SELECT id, candidate_no, name, abteilung, msh_user, active, created_at '
                                   'FROM trainee ORDER BY id')).all()
    assert [(r.id, r.candidate_no, r.name, r.abteilung, r.msh_user, r.active) for r in rows] == [
        (3, 'K-00001', 'Siti Rahma', None, None, False), (7, 'K-00002', 'Budi Santoso', 'Berlin', 'budi', True)]
    assert rows[1].created_at == datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    report = db.session.execute(text('SELECT period, hours, learned, station FROM training_report')).one()
    assert tuple(report) == ('2026-09-10', 6.5, 'Konjunktiv II', 'Wärmepumpe')
    assert db.session.execute(text('SELECT count(*) FROM leiter_rating')).scalar() == 1

    admin, budi = as_user('root_admin'), as_user('budi')
    assert admin.get('/api/candidates').get_json()['total'] == 2
    assert budi.get('/api/me').get_json()['roles'] == ['CANDIDATE']
    assert budi.get('/api/training/me').get_json()['reports'][0]['learned'] == 'Konjunktiv II'
    old = [a['summary'] for a in admin.get('/api/activity').get_json()['activity']]
    assert old == ['Bewertung Budi']
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    course = admin.post('/api/courses', json={'name': 'Kurs Bestand', 'level_id': b1}).get_json()['id']
    assert admin.post(f'/api/courses/{course}/participants', json={'trainee_ids': [7]}).status_code == 200
    assert admin.patch('/api/candidates/7', json={'current_level_id': b1}).status_code == 200
    db.session.commit()
    with pytest.raises(Exception, match='unveraenderlich'):
        db.session.execute(text("UPDATE activity_log SET summary = 'x'"))
    db.session.rollback()


def test_0016_fachrichtung_leer_aus_dem_alten_monitoring(app, db):
    """The old input field "Fach (Elektro / SHK / leer)" literally stored "leer" — that's not a specialization."""
    _migrate(downgrade, revision='0015')
    db.session.execute(text(
        "INSERT INTO trainee (name, fach, created_at) VALUES ('A', 'leer', now()), ('B', ' LEER ', now()), "
        "('C', 'shk', now()), ('D', 'Elektro', now()), ('E', NULL, now())"))
    _migrate(upgrade)
    assert db.session.execute(text('SELECT name, fach FROM trainee ORDER BY name')).all() == [
        ('A', None), ('B', None), ('C', 'SHK'), ('D', 'Elektro'), ('E', None)]


def test_bestand_aus_main_0017_abteilungen_und_alte_bewertungen(app, db, as_user):
    """main runs 0017: the department results from the part before " – ", old staff ratings remain
    unchanged in `leiter_rating` (the overall rating only reads `staff_rating`)."""
    _migrate(downgrade, revision='0017')
    db.session.execute(text(
        "INSERT INTO trainee (id, name, abteilung, created_at) VALUES (5, 'Budi', 'Erkelenz – PV-Assistent', now()),"
        "(6, 'Siti', 'Erkelenz – Elektro-Assistent', now()), (7, 'Dewi', 'Netzantrag', now()),"
        "(8, 'Rina', 'Berlin - PV-Assistent', now()), (9, 'Agus', NULL, now()), (10, 'Eka', '  ', now())"))
    db.session.execute(text(
        "INSERT INTO leiter_rating (trainee_id, rater, r_language, created_at) VALUES (5, 'anna_hr', 8, now())"))
    _migrate(upgrade)
    rows = db.session.execute(text(
        'SELECT t.id, d.name FROM trainee t LEFT JOIN department d ON d.id = t.department_id ORDER BY t.id')).all()
    assert [tuple(r) for r in rows] == [(5, 'Erkelenz'), (6, 'Erkelenz'), (7, 'Netzantrag'), (8, 'Berlin'),
                                        (9, None), (10, None)]
    assert db.session.execute(text('SELECT name FROM department ORDER BY name')).scalars().all() == [
        'Berlin', 'Erkelenz', 'Netzantrag']
    row = db.session.execute(text('SELECT rater, r_language, updated_at FROM leiter_rating')).one()
    assert tuple(row) == ('anna_hr', 8, None)
    assert db.session.execute(text('SELECT count(*) FROM staff_rating')).scalar() == 0
    assert as_user('root_admin').get('/api/overall').status_code == 200


def test_0021_modul_und_einheit_aus_dem_termin(app, db, as_user):
    """Existing data (one rating per session) gets the module + unit of the session; downgrade removes what the old
    schema cannot hold (second module per session, gaps) and shortens strength/target to one code."""
    _migrate(downgrade, revision='0020')
    db.session.execute(text(
        "INSERT INTO program (id, name, active, created_at) VALUES (90, 'P', true, now());"
        "INSERT INTO curriculum (id, program_id, level_id, status, created_at) "
        "  SELECT 90, 90, id, 'ACTIVE', now() FROM language_level ORDER BY id LIMIT 1;"
        "INSERT INTO course_module (id, curriculum_id, name, position, learning_objectives, status, created_at) VALUES "
        "  (91, 90, 'Modul 1', 1, '[]', 'ACTIVE', now()), (92, 90, 'Modul 2', 2, '[]', 'ACTIVE', now());"
        "INSERT INTO course (id, name, level_id, module_id, status, created_at) "
        "  SELECT 90, 'Gruppe', id, 91, 'RUNNING', now() FROM language_level ORDER BY id LIMIT 1;"
        "INSERT INTO course_session (id, course_id, module_id, starts_at, ends_at, status, cancel_reason, created_at) "
        "VALUES (91, 90, 91, '2026-10-01 06:00+00', '2026-10-01 08:00+00', 'COMPLETED', NULL, now()),"
        "  (92, 90, 91, '2026-10-02 06:00+00', '2026-10-02 08:00+00', 'CANCELLED', 'Feiertag', now()),"
        "  (93, 90, 91, '2026-10-05 06:00+00', '2026-10-05 08:00+00', 'COMPLETED', NULL, now()),"
        "  (94, 90, 92, '2026-10-06 06:00+00', '2026-10-06 08:00+00', 'COMPLETED', NULL, now());"
        "INSERT INTO trainee (id, name, created_at) VALUES (95, 'Budi', now());"
        "INSERT INTO lesson_rating (session_id, trainee_id, v, r, w, f, p, pu, mi, ha, strength, target, created_at) "
        "  VALUES (91, 95, 3, 3, 3, 3, 3, 1, 2, NULL, 'V', 'P', now()), (93, 95, 2, 2, 2, 2, 2, 1, 1, 1, 'W', 'L', now()),"
        "         (94, 95, 1, 1, 1, 1, 1, 0, 0, 0, 'L', 'R', now())"))
    _migrate(upgrade)
    rows = db.session.execute(text(
        'SELECT session_id, module_id, unit, strength FROM lesson_rating ORDER BY session_id')).all()
    assert [tuple(r) for r in rows] == [(91, 91, 1, 'V'), (93, 91, 2, 'W'), (94, 92, 1, 'L')]   # cancelled doesn't count
    db.session.execute(text(
        "INSERT INTO lesson_rating (session_id, module_id, unit, trainee_id, v, strength, created_at) "
        "VALUES (91, 92, 1, 95, 3, 'V,R', now()); UPDATE lesson_rating SET target = 'R,L' WHERE session_id = 94"))
    _migrate(downgrade, revision='0020')
    rows = db.session.execute(text('SELECT session_id, strength, target FROM lesson_rating ORDER BY session_id')).all()
    assert [tuple(r) for r in rows] == [(91, 'V', 'P'), (93, 'W', 'L'), (94, 'L', 'R')]
    _migrate(upgrade)
    assert as_user('root_admin').get('/api/courses/90/lesson-report').status_code == 200


def test_0023_bisherige_bewertungen_sind_monat_1(app, db):
    """All existing staff ratings belong to program month 1; one rating per candidate, rater and month."""
    _migrate(downgrade, revision='0022')
    db.session.execute(text(
        "INSERT INTO trainee (id, name, created_at) VALUES (96, 'Sari', now());"
        "INSERT INTO staff_rating (trainee_id, rater, kind, r_practical, r_reliability, r_motivation, created_at) "
        "VALUES (96, 'hanan', 'SPV', 7, 6, 5, '2026-10-26 03:00+00'), (96, 'mila', 'INTERN', 5, 5, 5, now())"))
    _migrate(upgrade)
    assert db.session.execute(text('SELECT array_agg(month ORDER BY rater) FROM staff_rating')).scalar() == [1, 1]
    with pytest.raises(Exception, match='uq_staff_rating_month'):
        db.session.execute(text(
            "INSERT INTO staff_rating (trainee_id, rater, kind, month, r_practical, r_reliability, r_motivation, "
            "created_at) VALUES (96, 'hanan', 'SPV', 1, 7, 7, 7, now())"))
    db.session.rollback()
    with pytest.raises(Exception, match='ck_staff_rating_month'):
        db.session.execute(text(
            "INSERT INTO staff_rating (trainee_id, rater, kind, month, r_practical, r_reliability, r_motivation, "
            "created_at) VALUES (96, 'hanan', 'SPV', 4, 7, 7, 7, now())"))
    db.session.rollback()

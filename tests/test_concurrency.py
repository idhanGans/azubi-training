"""Gleichzeitige Zugriffe gegen das echte Postgres: zwei Anfragen im selben Augenblick (zwei Threads).
Doppelbuchungen und doppelte Anwesenheit duerfen auch dann nicht entstehen — und nie ein 500."""
import threading
from datetime import timedelta

import pytest

from app.services.local_time import today

ROUNDS = 5


def _together(*calls):
    """Alle Aufrufe exakt gleichzeitig starten (Barriere) und die Antworten zurueckgeben."""
    barrier, results = threading.Barrier(len(calls)), [None] * len(calls)

    def run(i, call):
        barrier.wait()
        results[i] = call()
    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return results


@pytest.fixture
def two_courses(as_user, grant, trainee):
    """Dozentin Maria unterrichtet zwei Kurse (je ein Kandidat) — ein Termin zur selben Zeit waere eine Doppelbuchung."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    maria = admin.post('/api/instructors', json={'name': 'Maria', 'msh_user': 'maria', 'level_ids': [b1]}).get_json()['id']
    grant('maria', 'INSTRUCTOR')
    budi, dewi = trainee('Budi'), trainee('Dewi')
    k1 = admin.post('/api/courses', json={'name': 'Kurs A', 'level_id': b1, 'instructor_id': maria}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs B', 'level_id': b1, 'instructor_id': maria}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})
    return {'admin': admin, 'maria': as_user('maria'), 'k1': k1, 'k2': k2, 'budi': budi}


def test_gleichzeitige_termine_derselben_dozentin_nur_einer_gewinnt(two_courses):
    admin, day = two_courses['admin'], today() + timedelta(days=7)
    for n in range(ROUNDS):
        slot = {'date': day.isoformat(), 'start': f'{8 + 2 * n:02d}:00', 'end': f'{9 + 2 * n:02d}:00'}
        codes = sorted(r.status_code for r in _together(
            lambda: admin.post('/api/sessions', json={'course_id': two_courses['k1'], **slot}),
            lambda: admin.post('/api/sessions', json={'course_id': two_courses['k2'], **slot})))
        assert codes == [201, 409], f'Runde {n}: {codes}'
    listed = admin.get(f'/api/sessions?from={day.isoformat()}&to={day.isoformat()}').get_json()['sessions']
    assert len(listed) == ROUNDS                                  # je Zeitfenster genau ein Termin


def test_gleichzeitig_erfasste_anwesenheit_ergibt_einen_eintrag(two_courses, db):
    from app.models.attendance import Attendance
    admin, maria = two_courses['admin'], two_courses['maria']
    for n in range(ROUNDS):
        past = (today() - timedelta(days=n + 1)).isoformat()
        sid = admin.post('/api/sessions', json={'course_id': two_courses['k1'], 'date': past, 'start': '10:00',
                                                'end': '11:00'}).get_json()['sessions'][0]['id']
        body = lambda status: {'entries': [{'trainee_id': two_courses['budi'], 'status': status}]}
        codes = [r.status_code for r in _together(
            lambda: maria.put(f'/api/sessions/{sid}/attendance', json=body('PRESENT')),
            lambda: admin.put(f'/api/sessions/{sid}/attendance', json=body('LATE')))]
        assert all(c < 500 for c in codes), f'Runde {n}: {codes}'
        assert Attendance.query.filter_by(session_id=sid).count() == 1
        db.session.expire_all()


def test_doppelte_anwesenheit_scheitert_an_der_datenbank(two_courses, db):
    """Die UNIQUE-Regel (Termin + Kandidat) haelt auch ohne die App-Logik davor."""
    from sqlalchemy.exc import IntegrityError

    from app.models.attendance import Attendance
    past = (today() - timedelta(days=1)).isoformat()
    sid = two_courses['admin'].post('/api/sessions', json={'course_id': two_courses['k1'], 'date': past,
                                                          'start': '10:00', 'end': '11:00'}).get_json()['sessions'][0]['id']
    for _ in range(2):
        db.session.add(Attendance(session_id=sid, trainee_id=two_courses['budi'], status='PRESENT', recorded_by='x'))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

"""Anwesenheit: Erfassen/Korrigieren, keine Doppel-Eintraege, Quote, Reichweite, Rechte."""
from datetime import timedelta

import pytest

from app.services.local_time import today


@pytest.fixture
def att(as_user, grant, trainee):
    """Kurs Maria (Budi, Sari) und Kurs Tom (Dewi), je ein vergangener Termin; Maria/Tom sind Dozenten."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [b1]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    budi, sari, dewi = trainee('Budi', msh_user='budi'), trainee('Sari', msh_user='sari'), trainee('Dewi')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'instructor_id': ids['maria']}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1, 'instructor_id': ids['tom']}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi, sari]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})

    def session(course, days_ago=7, start='10:00', end='12:00'):
        day = (today() - timedelta(days=days_ago)).isoformat()
        res = admin.post('/api/sessions', json={'course_id': course, 'date': day, 'start': start, 'end': end})
        return res.get_json()['sessions'][0]['id']

    return {'admin': admin, 'maria': as_user('maria'), 'tom': as_user('tom'), 'budi': budi, 'sari': sari,
            'dewi': dewi, 'k1': k1, 'k2': k2, 'session': session, 's1': session(k1), 's2': session(k2, start='14:00',
                                                                                                     end='15:00')}


def _put(client, sid, *entries):
    return client.put(f'/api/sessions/{sid}/attendance', json={'entries': list(entries)})


def test_erfassen_setzt_termin_auf_durchgefuehrt(att):
    res = _put(att['maria'], att['s1'], {'trainee_id': att['budi'], 'status': 'PRESENT'},
               {'trainee_id': att['sari'], 'status': 'LATE', 'minutes_late': 10, 'note': 'Bus'})
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body['session']['status'] == 'COMPLETED'
    assert body['summary'] == {'recorded': 2, 'expected': 2, 'rate': 1.0}
    assert [e['attendance']['status'] for e in body['entries']] == ['PRESENT', 'LATE']
    log = att['admin'].get('/api/activity').get_json()['activity'][0]
    assert log['action'] == 'attendance.record'
    assert log['detail']['changes'] == {'Budi': [None, 'Anwesend'], 'Sari': [None, 'Verspätet (10 Min.)']}


def test_korrektur_statt_doppeleintrag(att, db):
    from app.models.attendance import Attendance
    _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'ABSENT'})
    res = _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'EXCUSED', 'note': 'krank'})
    assert res.status_code == 200
    assert Attendance.query.filter_by(session_id=att['s1'], trainee_id=att['sari']).count() == 1
    log = att['admin'].get('/api/activity').get_json()['activity'][0]
    assert log['detail']['changes'] == {'Sari': ['Abwesend', 'Entschuldigt']}
    unchanged = _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'EXCUSED', 'note': 'krank'})
    assert unchanged.status_code == 200
    assert att['admin'].get('/api/activity').get_json()['activity'][0]['id'] == log['id']   # nichts Neues


@pytest.mark.parametrize('entries', [
    [],
    [{'trainee_id': 'budi', 'status': 'PRESENT'}],
    [{'status': 'PRESENT'}],
    [{'trainee_id': 'BUDI', 'status': 'DA'}],
    [{'trainee_id': 'BUDI', 'status': 'LATE', 'minutes_late': 0}],
    [{'trainee_id': 'BUDI', 'status': 'PRESENT'}, {'trainee_id': 'BUDI', 'status': 'ABSENT'}],
    [{'trainee_id': 'DEWI', 'status': 'PRESENT'}],                     # nicht in diesem Kurs
])
def test_ungueltige_eintraege(att, entries):
    ids = {'BUDI': att['budi'], 'DEWI': att['dewi']}
    entries = [{**e, 'trainee_id': ids.get(e.get('trainee_id'), e.get('trainee_id'))} if 'trainee_id' in e else e
               for e in entries]
    res = att['maria'].put(f'/api/sessions/{att["s1"]}/attendance', json={'entries': entries})
    assert res.status_code == 400 and res.get_json()['field'] == 'entries'


def test_nicht_vor_beginn_und_nicht_bei_absage(att):
    future = att['session'](att['k1'], days_ago=-3)
    res = _put(att['maria'], future, {'trainee_id': att['budi'], 'status': 'PRESENT'})
    assert res.status_code == 409 and 'erst ab Beginn' in res.get_json()['error']
    att['admin'].patch(f'/api/sessions/{att["s2"]}', json={'status': 'CANCELLED', 'cancel_reason': 'krank'})
    res = _put(att['admin'], att['s2'], {'trainee_id': att['dewi'], 'status': 'PRESENT'})
    assert res.status_code == 409


def test_archivierter_kandidat_bekommt_keinen_neuen_eintrag(att):
    att['admin'].post(f'/api/candidates/{att["sari"]}/archive')
    assert _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'PRESENT'}).status_code == 400


def test_quote_zaehlt_entschuldigt_nicht_und_abgesagte_nicht(att):
    admin, budi = att['admin'], att['budi']
    sessions = [att['s1']] + [att['session'](att['k1'], days_ago=d) for d in (6, 5, 4)]
    for sid, status in zip(sessions, ('PRESENT', 'LATE', 'EXCUSED', 'ABSENT')):
        _put(admin, sid, {'trainee_id': budi, 'status': status})
    stats = admin.get(f'/api/candidates/{budi}').get_json()['attendance']['stats']
    assert stats == {'present': 1, 'late': 1, 'excused': 1, 'absent': 1, 'recorded': 4, 'rate': 0.6667}
    admin.patch(f'/api/sessions/{sessions[3]}', json={'status': 'CANCELLED', 'cancel_reason': 'Fehler'})
    assert admin.get(f'/api/candidates/{budi}').get_json()['attendance']['stats']['rate'] == 1.0
    items = {c['name']: c['attendance_rate'] for c in admin.get('/api/candidates').get_json()['items']}
    assert items == {'Budi': 1.0, 'Dewi': None, 'Sari': None}             # ohne Eintraege: keine Quote


def test_dozent_nur_eigene_kurse(att):
    assert _put(att['maria'], att['s2'], {'trainee_id': att['dewi'], 'status': 'PRESENT'}).status_code == 404
    assert att['maria'].get(f'/api/sessions/{att["s2"]}/attendance').status_code == 404
    # Budi auch in Toms Kurs: Maria sieht die Quote nur ueber IHRE Kurse
    att['admin'].post(f'/api/courses/{att["k2"]}/participants', json={'trainee_ids': [att['budi']]})
    _put(att['maria'], att['s1'], {'trainee_id': att['budi'], 'status': 'PRESENT'})
    _put(att['tom'], att['s2'], {'trainee_id': att['budi'], 'status': 'ABSENT'})
    assert att['maria'].get(f'/api/candidates/{att["budi"]}').get_json()['attendance']['stats']['rate'] == 1.0
    assert att['admin'].get(f'/api/candidates/{att["budi"]}').get_json()['attendance']['stats']['rate'] == 0.5


def test_kandidat_sieht_nur_eigene_ohne_notiz(att, as_user):
    _put(att['maria'], att['s1'], {'trainee_id': att['budi'], 'status': 'LATE', 'minutes_late': 5, 'note': 'intern'},
         {'trainee_id': att['sari'], 'status': 'ABSENT'})
    body = as_user('budi').get('/api/my-attendance').get_json()
    assert body['stats']['rate'] == 1.0 and len(body['records']) == 1
    assert body['records'][0] == {**body['records'][0], 'status': 'LATE', 'minutes_late': 5}
    assert 'note' not in body['records'][0] and 'notes' not in body['records'][0]['session']
    assert as_user('sari').get('/api/my-attendance').get_json()['stats']['rate'] == 0.0
    assert as_user('budi').get(f'/api/sessions/{att["s1"]}/attendance').status_code == 403
    assert att['maria'].get('/api/my-attendance').status_code == 403


@pytest.mark.parametrize('role,lesen,erfassen', [
    ('HR', 200, 403), ('MANAGEMENT', 200, 403), ('ACADEMIC_MANAGER', 200, 200),
])
def test_rechte(att, as_user, grant, role, lesen, erfassen):
    grant('person', role)
    client = as_user('person')
    assert client.get(f'/api/sessions/{att["s1"]}/attendance').status_code == lesen
    assert _put(client, att['s1'], {'trainee_id': att['budi'], 'status': 'PRESENT'}).status_code == erfassen


def test_offene_anwesenheit_in_mein_unterricht(att):
    stats = att['maria'].get('/api/my-teaching').get_json()['stats']
    assert stats['open_attendance_count'] == 1
    _put(att['maria'], att['s1'], {'trainee_id': att['budi'], 'status': 'PRESENT'})
    assert att['maria'].get('/api/my-teaching').get_json()['stats']['open_attendance_count'] == 1   # Sari fehlt
    _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'EXCUSED'})
    assert att['maria'].get('/api/my-teaching').get_json()['stats']['open_attendance_count'] == 0


def test_quote_je_teilnehmer_im_kurs(att):
    _put(att['maria'], att['s1'], {'trainee_id': att['budi'], 'status': 'ABSENT'})
    rows = {p['name']: p['attendance'] for p in att['admin'].get(f'/api/courses/{att["k1"]}').get_json()['participants']}
    assert rows['Budi']['rate'] == 0.0 and rows['Sari'] is None


def test_gruppenwechsel_bleibt_korrigierbar(att):
    """Wer die Gruppe gewechselt hat, bleibt in den alten Terminen korrigierbar; wer nie drin war, nicht."""
    assert _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'ABSENT'}).status_code == 200
    att['admin'].delete(f'/api/courses/{att["k1"]}/participants/{att["sari"]}', json={})
    res = _put(att['maria'], att['s1'], {'trainee_id': att['sari'], 'status': 'EXCUSED', 'note': 'Attest'})
    assert res.status_code == 200, res.get_json()
    sari = next(e for e in res.get_json()['entries'] if e['trainee']['id'] == att['sari'])
    assert (sari['trainee']['in_course'], sari['attendance']['status']) == (False, 'EXCUSED')
    log = att['admin'].get('/api/activity?action=attendance.record').get_json()['activity'][0]
    assert log['detail']['changes']['Sari'] == ['Abwesend', 'Entschuldigt']
    assert _put(att['maria'], att['s1'], {'trainee_id': att['dewi'], 'status': 'PRESENT'}).status_code == 400

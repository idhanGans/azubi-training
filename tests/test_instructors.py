"""Dozenten: Stammdaten, Niveaus, Verfuegbarkeit, Login-Regeln, Archivieren."""
import pytest


def _levels(client):
    return {e['code']: e['id'] for e in client.get('/api/catalogs/language-level').get_json()['entries']}


def _maria(client, **extra):
    lv = _levels(client)
    body = {'name': 'Maria Weber', 'email': 'maria@example.de', 'msh_user': 'Maria_Weber',
            'qualification': 'DaF-Lehrerin', 'specialization': 'Prüfungsvorbereitung',
            'level_ids': [lv['B1'], lv['A2'], lv['B1']],
            'availability': [{'weekday': 2, 'start': '13:00', 'end': '17:00'},
                             {'weekday': 0, 'start': '08:00', 'end': '12:00'}], **extra}
    return client.post('/api/instructors', json=body)


def test_dozent_anlegen_und_lesen(as_user, grant):
    admin = as_user('root_admin')
    res = _maria(admin)
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body['msh_user'] == 'maria_weber'
    assert [lv['code'] for lv in body['levels']] == ['A2', 'B1']          # sortiert, ohne Doppelte
    assert [s['weekday'] for s in body['availability']] == [0, 2]
    assert body['status'] == 'ACTIVE'
    row = admin.get('/api/instructors').get_json()['instructors'][0]
    assert row['course_count'] == 0 and row['has_instructor_role'] is False
    grant('maria_weber', 'INSTRUCTOR')
    assert admin.get('/api/instructors').get_json()['instructors'][0]['has_instructor_role'] is True


@pytest.mark.parametrize('extra,feld', [
    ({'name': ''}, 'name'),
    ({'email': 'keine-mail'}, 'email'),
    ({'status': 'KRANK'}, 'status'),
    ({'level_ids': [9999]}, 'level_ids'),
    ({'level_ids': 'B1'}, 'level_ids'),
    ({'availability': [{'weekday': 7, 'start': '08:00', 'end': '09:00'}]}, 'availability'),
    ({'availability': [{'weekday': 1, 'start': '8 Uhr', 'end': '09:00'}]}, 'availability'),
    ({'availability': [{'weekday': 1, 'start': '12:00', 'end': '09:00'}]}, 'availability'),
    ({'availability': [{'weekday': 1, 'start': '08:00', 'end': '09:00'},
                       {'weekday': 1, 'start': '10:00', 'end': '11:00'}]}, 'availability'),
])
def test_ungueltige_eingaben(as_user, extra, feld):
    res = _maria(as_user('root_admin'), **extra)
    assert res.status_code == 400
    assert res.get_json()['field'] == feld


def test_login_regeln(as_user, trainee):
    admin = as_user('root_admin')
    trainee('Budi', msh_user='budi')
    res = _maria(admin, msh_user='budi')
    assert res.status_code == 409 and res.get_json()['field'] == 'msh_user'
    assert _maria(admin).status_code == 201
    dup = admin.post('/api/instructors', json={'name': 'Zweite', 'msh_user': 'maria_weber'})
    assert dup.status_code == 409
    # umgekehrt: ein Dozenten-Login wird kein Kandidat
    assert admin.post('/api/candidates', json={'name': 'X', 'msh_user': 'maria_weber'}).status_code == 409


def test_aenderung_wird_mit_alt_und_neu_protokolliert(as_user):
    admin = as_user('root_admin')
    iid = _maria(admin).get_json()['id']
    lv = _levels(admin)
    admin.patch(f'/api/instructors/{iid}', json={'status': 'ON_LEAVE', 'level_ids': [lv['C1']]})
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert log['action'] == 'instructor.update'
    assert log['detail']['changes'] == {'status': ['ACTIVE', 'ON_LEAVE'], 'levels': [['A2', 'B1'], ['C1']]}


@pytest.mark.parametrize('role,lesen,pflegen', [
    ('HR', 200, 201), ('ACADEMIC_MANAGER', 200, 201), ('MANAGEMENT', 200, 403), ('INSTRUCTOR', 403, 403),
])
def test_rechte(as_user, grant, role, lesen, pflegen):
    grant('person', role)
    client = as_user('person')
    assert client.get('/api/instructors').status_code == lesen
    assert client.post('/api/instructors', json={'name': 'Neu'}).status_code == pflegen


def test_kandidat_hat_keinen_zugriff(as_user, trainee):
    trainee('Budi', msh_user='budi')
    assert as_user('budi').get('/api/instructors').status_code == 403


def test_archivieren_nur_ohne_offene_kurse(as_user):
    admin = as_user('root_admin')
    iid = _maria(admin).get_json()['id']
    cid = admin.post('/api/courses', json={'name': 'B1 Herbst', 'level_id': _levels(admin)['B1'],
                                           'instructor_id': iid}).get_json()['id']
    res = admin.post(f'/api/instructors/{iid}/archive')
    assert res.status_code == 409 and 'B1 Herbst' in res.get_json()['error']
    admin.patch(f'/api/courses/{cid}', json={'status': 'COMPLETED'})
    assert admin.post(f'/api/instructors/{iid}/archive').get_json()['archived_at']
    assert admin.get('/api/instructors').get_json()['instructors'] == []
    assert len(admin.get('/api/instructors?archived=1').get_json()['instructors']) == 1
    assert admin.post(f'/api/instructors/{iid}/restore').get_json()['archived_at'] is None

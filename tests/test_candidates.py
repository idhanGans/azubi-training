"""Kandidatenverwaltung: Anlegen/Pflege, Pruefungen, Archiv, Profil, Protokoll."""
import pytest


def _levels(client):
    return {e['code']: e['id'] for e in client.get('/api/catalogs/language-level').get_json()['entries']}


def _statuses(client):
    return {e['code']: e['id'] for e in client.get('/api/catalogs/candidate-status').get_json()['entries']}


def test_kandidaten_nr_wird_fortlaufend_vergeben(as_user):
    admin = as_user('root_admin')
    first = admin.post('/api/candidates', json={'name': 'Anna'}).get_json()
    second = admin.post('/api/candidates', json={'name': 'Budi'}).get_json()
    assert (first['candidate_no'], second['candidate_no']) == ('K-00001', 'K-00002')
    assert first['created_by'] == 'root_admin'


def test_anlegen_mit_allen_feldern(as_user):
    admin = as_user('root_admin')
    lv, st = _levels(admin), _statuses(admin)
    res = admin.post('/api/candidates', json={
        'name': 'Budi Santoso', 'email': 'budi@example.org', 'phone': '+62 812 3456 789',
        'date_of_birth': '2002-04-17', 'fach': 'Elektro', 'target_occupation': 'Elektroniker',
        'status_id': st['LANGUAGE_COURSE'], 'current_level_id': lv['A2'], 'target_level_id': lv['B1'],
        'start_date': '2026-09-01', 'expected_completion_date': '2027-03-31'})
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body['status']['name'] == 'Im Sprachkurs'
    assert (body['current_level']['code'], body['target_level']['code']) == ('A2', 'B1')
    assert body['date_of_birth'] == '2002-04-17'


@pytest.mark.parametrize('payload,feld', [
    ({'name': '  '}, 'name'),
    ({'name': 'X', 'email': 'keine-mail'}, 'email'),
    ({'name': 'X', 'phone': 'abc'}, 'phone'),
    ({'name': 'X', 'date_of_birth': '2999-01-01'}, 'date_of_birth'),
    ({'name': 'X', 'start_date': '2026-09-01', 'expected_completion_date': '2026-08-01'}, 'expected_completion_date'),
    ({'name': 'X', 'fach': 'Maler'}, 'fach'),
    ({'name': 'X', 'status_id': 99999}, 'status_id'),
])
def test_ungueltige_eingaben(as_user, payload, feld):
    res = as_user('root_admin').post('/api/candidates', json=payload)
    assert res.status_code == 400 and res.get_json()['field'] == feld


def test_zielniveau_nicht_unter_aktuellem(as_user):
    admin = as_user('root_admin')
    lv = _levels(admin)
    res = admin.post('/api/candidates', json={'name': 'X', 'current_level_id': lv['B1'], 'target_level_id': lv['A2']})
    assert res.status_code == 400 and res.get_json()['field'] == 'target_level_id'
    cid = admin.post('/api/candidates', json={'name': 'Y', 'target_level_id': lv['A2']}).get_json()['id']
    res = admin.patch(f'/api/candidates/{cid}', json={'current_level_id': lv['B2']})
    assert res.status_code == 400   # Querpruefung auch gegen den gespeicherten Wert


def test_deaktivierter_status_bleibt_aber_ist_nicht_neu_waehlbar(as_user):
    admin = as_user('root_admin')
    st = _statuses(admin)
    a = admin.post('/api/candidates', json={'name': 'A', 'status_id': st['PAUSED']}).get_json()['id']
    admin.patch(f'/api/catalogs/candidate-status/{st["PAUSED"]}', json={'active': False})
    assert admin.patch(f'/api/candidates/{a}', json={'status_id': st['PAUSED'], 'name': 'A2'}).status_code == 200
    res = admin.post('/api/candidates', json={'name': 'B', 'status_id': st['PAUSED']})
    assert res.status_code == 400


def test_aenderung_wird_mit_alt_und_neu_protokolliert(as_user):
    admin = as_user('root_admin')
    st = _statuses(admin)
    cid = admin.post('/api/candidates', json={'name': 'Budi', 'fach': 'SHK'}).get_json()['id']
    res = admin.patch(f'/api/candidates/{cid}', json={'fach': 'Elektro', 'status_id': st['EXAM_PREPARATION']})
    assert res.get_json()['updated_by'] == 'root_admin'
    eintrag = admin.get('/api/activity').get_json()['activity'][0]
    assert eintrag['detail'] == {'changes': {'fach': ['SHK', 'Elektro'],
                                             'status': [None, 'Prüfungsvorbereitung']}}


def test_patch_ohne_aenderung_schreibt_kein_protokoll(as_user):
    admin = as_user('root_admin')
    cid = admin.post('/api/candidates', json={'name': 'Budi'}).get_json()['id']
    admin.patch(f'/api/candidates/{cid}', json={'name': 'Budi'})
    assert [e['action'] for e in admin.get('/api/activity').get_json()['activity']] == ['trainee.create']


def test_archivieren_behaelt_historie_und_sperrt_portal(as_user, trainee, grant):
    grant('hr', 'HR')
    tid = trainee('Anna', msh_user='anna')
    assert as_user('anna').post('/api/training/me', json={'hours': 5}).status_code == 201
    res = as_user('hr').post(f'/api/candidates/{tid}/archive')
    assert res.status_code == 200 and res.get_json()['archived_by'] == 'hr'
    assert as_user('hr').get('/api/candidates').get_json()['total'] == 0
    assert as_user('hr').get('/api/candidates?archived=1').get_json()['total'] == 1
    assert as_user('hr').get(f'/api/candidates/{tid}').get_json()['training']['report_count'] == 1
    anna = as_user('anna')
    assert anna.get('/api/me').get_json()['roles'] == []   # KEIN Rueckfall auf Team
    assert anna.get('/api/training/me').status_code == 403


def test_wiederherstellen(as_user, trainee, grant):
    grant('hr', 'HR')
    tid = trainee('Anna', msh_user='anna')
    as_user('hr').post(f'/api/candidates/{tid}/archive')
    assert as_user('hr').post(f'/api/candidates/{tid}/restore').get_json()['archived_at'] is None
    assert as_user('anna').get('/api/training/me').status_code == 200


def test_loeschen_gibt_es_nicht(as_user, trainee):
    tid = trainee('Anna')
    assert as_user('root_admin').delete(f'/api/candidates/{tid}').status_code == 405


def test_login_konflikte(as_user, trainee, grant):
    trainee('Anna', msh_user='anna')
    admin = as_user('root_admin')
    res = admin.post('/api/candidates', json={'name': 'Andere', 'msh_user': 'ANNA'})
    assert res.status_code == 409 and res.get_json()['field'] == 'msh_user'
    grant('dozent1', 'INSTRUCTOR')
    tid = trainee('Budi')
    assert admin.patch(f'/api/candidates/{tid}', json={'msh_user': 'dozent1'}).status_code == 409


def test_profil(as_user, trainee):
    tid = trainee('Anna', msh_user='anna')
    as_user('anna').post('/api/training/me', json={'hours': 4})
    as_user('root_admin').post('/api/ratings', json={'trainee_id': tid, 'r_practical': 8, 'r_reliability': 7, 'r_motivation': 9})
    body = as_user('root_admin').get(f'/api/candidates/{tid}').get_json()
    assert body['candidate']['name'] == 'Anna'
    assert [(r['kind'], r['r_practical']) for r in body['ratings']] == [('INTERN', 8)]
    assert body['training']['hours_total'] == 4
    assert as_user('root_admin').get('/api/candidates/999').status_code == 404


def test_kennzahlen_fuers_monitoring(as_user, trainee):
    trainee('Anna', msh_user='anna')
    anna = as_user('anna')
    anna.post('/api/training/me', json={'period': '2026-09-20', 'hours': 6, 'lang': True})
    anna.post('/api/training/me', json={'period': '2026-09-20', 'hours': 2, 'tech': True})
    anna.post('/api/training/me', json={'period': '2026-09-21', 'hours': 4.5, 'lang': True})
    row = as_user('root_admin').get('/api/trainees').get_json()['trainees'][0]
    assert (row['hours_total'], row['report_count'], row['days_reported']) == (12.5, 3, 2)
    assert (row['lang_count'], row['tech_count']) == (2, 1)

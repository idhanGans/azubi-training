"""Curriculum: Programm -> Niveau -> Curriculum -> Module, Rechte, Reihenfolge."""
import pytest


def _level(client, code):
    return next(e['id'] for e in client.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == code)


@pytest.fixture
def b1_curriculum(as_user):
    admin = as_user('root_admin')
    pid = admin.post('/api/programs', json={'name': 'Deutschsprachkurs'}).get_json()['id']
    return admin.post(f'/api/programs/{pid}/curricula', json={'level_id': _level(admin, 'B1')}).get_json()['id']


def test_programm_mit_mehreren_niveaus(as_user):
    admin = as_user('root_admin')
    pid = admin.post('/api/programs', json={'name': 'Deutschsprachkurs'}).get_json()['id']
    for code in ('B1', 'A2'):
        assert admin.post(f'/api/programs/{pid}/curricula', json={'level_id': _level(admin, code)}).status_code == 201
    dup = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': _level(admin, 'A2')})
    assert dup.status_code == 409
    program = admin.get('/api/programs').get_json()['programs'][0]
    assert [c['level']['code'] for c in program['curricula']] == ['A2', 'B1']   # nach Niveau sortiert
    assert admin.post('/api/programs', json={'name': 'deutschsprachkurs'}).status_code == 409


def test_module_mit_lernzielen_und_reihenfolge(as_user, b1_curriculum):
    admin = as_user('root_admin')
    ids = [admin.post(f'/api/curricula/{b1_curriculum}/modules', json={
        'name': name, 'duration_hours': 12, 'learning_objectives': goals}).get_json()['id']
        for name, goals in (('Modul 7 – Perfekt', []),
                            ('Modul 8 – Konjunktiv II', ['Wünsche formulieren', ' ', 'Höfliche Bitten formulieren']))]
    body = admin.get(f'/api/curricula/{b1_curriculum}').get_json()
    assert [m['position'] for m in body['modules']] == [1, 2]
    assert body['modules'][1]['learning_objectives'] == ['Wünsche formulieren', 'Höfliche Bitten formulieren']
    assert body['modules'][1]['level']['code'] == 'B1'
    assert admin.put(f'/api/curricula/{b1_curriculum}/module-order', json={'module_ids': ids[::-1]}).status_code == 200
    assert [m['id'] for m in admin.get(f'/api/curricula/{b1_curriculum}').get_json()['modules']] == ids[::-1]
    bad = admin.put(f'/api/curricula/{b1_curriculum}/module-order', json={'module_ids': ids[:1]})
    assert bad.status_code == 400
    assert admin.get('/api/programs').get_json()['programs'][0]['curricula'][0]['hours_total'] == 24


def test_modul_aenderung_mit_alt_und_neu(as_user, b1_curriculum):
    admin = as_user('root_admin')
    mid = admin.post(f'/api/curricula/{b1_curriculum}/modules', json={'name': 'Modul 8'}).get_json()['id']
    admin.patch(f'/api/modules/{mid}', json={'status': 'ACTIVE', 'learning_objectives': ['Wünsche formulieren']})
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert log['detail']['changes'] == {'status': ['DRAFT', 'ACTIVE'],
                                        'learning_objectives': [[], ['Wünsche formulieren']]}


@pytest.mark.parametrize('payload,feld', [
    ({'name': ''}, 'name'),
    ({'name': 'X', 'duration_hours': 0}, 'duration_hours'),
    ({'name': 'X', 'status': 'FERTIG'}, 'status'),
    ({'name': 'X', 'learning_objectives': 'kein Array'}, 'learning_objectives'),
    ({'name': 'X', 'learning_objectives': ['x' * 301]}, 'learning_objectives'),
])
def test_modul_eingaben(as_user, b1_curriculum, payload, feld):
    res = as_user('root_admin').post(f'/api/curricula/{b1_curriculum}/modules', json=payload)
    assert res.status_code == 400 and res.get_json()['field'] == feld


@pytest.mark.parametrize('role,lesen,anlegen', [
    ('ACADEMIC_MANAGER', 200, 201), ('INSTRUCTOR', 200, 403), ('HR', 200, 403), ('MANAGEMENT', 200, 403),
])
def test_rechte(as_user, grant, b1_curriculum, role, lesen, anlegen):
    grant('person', role)
    client = as_user('person')
    assert client.get(f'/api/curricula/{b1_curriculum}').status_code == lesen
    assert client.post(f'/api/curricula/{b1_curriculum}/modules', json={'name': 'M'}).status_code == anlegen


def test_kandidat_sieht_kein_curriculum(as_user, trainee, b1_curriculum):
    trainee('Anna', msh_user='anna')
    assert as_user('anna').get('/api/programs').status_code == 403
    assert as_user('anna').get(f'/api/curricula/{b1_curriculum}').status_code == 403


def test_kandidat_bekommt_ein_programm(as_user):
    admin = as_user('root_admin')
    pid = admin.post('/api/programs', json={'name': 'Deutschsprachkurs'}).get_json()['id']
    cid = admin.post('/api/candidates', json={'name': 'Budi', 'program_id': pid}).get_json()['id']
    assert admin.get(f'/api/candidates/{cid}').get_json()['candidate']['program']['name'] == 'Deutschsprachkurs'
    admin.patch(f'/api/programs/{pid}', json={'active': False})
    assert admin.post('/api/candidates', json={'name': 'Neu', 'program_id': pid}).status_code == 400


def test_summe_der_module_kommt_vom_server(as_user, b1_curriculum):
    """Anzahl + Stunden zaehlen nur aktive Module — dieselbe Zahl wie in der Programm-Liste."""
    admin = as_user('root_admin')
    for name, hours, status in (('M1', 10, 'ACTIVE'), ('M2', 6.5, 'DRAFT'), ('M3', 20, 'ARCHIVED')):
        admin.post(f'/api/curricula/{b1_curriculum}/modules', json={'name': name, 'duration_hours': hours,
                                                                    'status': status})
    detail = admin.get(f'/api/curricula/{b1_curriculum}').get_json()['curriculum']
    assert (detail['module_count'], detail['hours_total']) == (2, 16.5)
    listed = admin.get('/api/programs').get_json()['programs'][0]['curricula'][0]
    assert (listed['module_count'], listed['hours_total']) == (2, 16.5)

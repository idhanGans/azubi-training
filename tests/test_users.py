"""Benutzerverwaltung: Rollen vergeben/entziehen, Konflikte, Protokoll."""


def test_rolle_vergeben_wirkt_sofort(as_user):
    admin = as_user('root_admin')
    assert as_user('anna').get('/api/trainees').status_code == 403
    res = admin.post('/api/users', json={'username': 'Anna', 'role': 'HR'})
    assert res.status_code == 201 and res.get_json()['username'] == 'anna'
    assert as_user('anna').get('/api/trainees').status_code == 200


def test_rolle_entziehen(as_user):
    admin = as_user('root_admin')
    rid = admin.post('/api/users', json={'username': 'anna', 'role': 'HR'}).get_json()['id']
    assert admin.delete(f'/api/users/{rid}').status_code == 200
    assert as_user('anna').get('/api/trainees').status_code == 403


def test_kandidat_bekommt_keine_team_rolle(as_user, trainee):
    trainee('Budi', msh_user='budi')
    res = as_user('root_admin').post('/api/users', json={'username': 'budi', 'role': 'HR'})
    assert res.status_code == 409


def test_unbekannte_rolle_und_doppelte_vergabe(as_user):
    admin = as_user('root_admin')
    assert admin.post('/api/users', json={'username': 'anna', 'role': 'CANDIDATE'}).status_code == 400
    assert admin.post('/api/users', json={'username': 'anna', 'role': 'HR'}).status_code == 201
    assert admin.post('/api/users', json={'username': 'anna', 'role': 'HR'}).status_code == 409


def test_eigene_super_admin_rolle_nicht_selbst_entziehen(as_user, grant):
    grant('zweiter_admin', 'SUPER_ADMIN')
    client = as_user('zweiter_admin')
    rid = client.get('/api/users').get_json()['assignments'][0]['id']
    assert client.delete(f'/api/users/{rid}').status_code == 409


def test_nur_super_admin_verwaltet_benutzer(as_user, grant):
    grant('hr', 'HR')
    assert as_user('hr').post('/api/users', json={'username': 'x1', 'role': 'HR'}).status_code == 403


def test_vergabe_wird_protokolliert(as_user):
    admin = as_user('root_admin')
    admin.post('/api/users', json={'username': 'anna', 'role': 'MANAGEMENT'})
    eintrag = admin.get('/api/activity').get_json()['activity'][0]
    assert (eintrag['action'], eintrag['entity_name']) == ('role.assign', 'anna')

"""Stammdaten: Startwerte, Pflege nur mit system.manage, kein Loeschen."""


def test_startwerte(as_user, grant):
    grant('hr', 'HR')
    hr = as_user('hr')
    statuses = [e['name'] for e in hr.get('/api/catalogs/candidate-status').get_json()['entries']]
    assert statuses == ['Interessent', 'Aufnahmeprüfung', 'Im Sprachkurs', 'Prüfungsvorbereitung',
                        'Bereit für Ausbildung', 'Abgeschlossen', 'Pausiert', 'Ausgeschieden']
    levels = [e['code'] for e in hr.get('/api/catalogs/language-level').get_json()['entries']]
    assert levels == ['A1', 'A2', 'B1', 'B2', 'C1']


def test_nur_super_admin_pflegt(as_user, grant):
    grant('hr', 'HR')
    assert as_user('hr').post('/api/catalogs/language-level', json={'code': 'C2', 'name': 'C2'}).status_code == 403
    admin = as_user('root_admin')
    res = admin.post('/api/catalogs/language-level', json={'code': 'c2', 'name': 'C2', 'sort_order': 60})
    assert res.status_code == 201 and res.get_json()['code'] == 'C2'
    assert admin.post('/api/catalogs/language-level', json={'code': 'C2', 'name': 'x'}).status_code == 409


def test_umbenennen_deaktivieren_wird_protokolliert(as_user):
    admin = as_user('root_admin')
    entry = admin.get('/api/catalogs/candidate-status').get_json()['entries'][0]
    res = admin.patch(f'/api/catalogs/candidate-status/{entry["id"]}', json={'name': 'Bewerber', 'active': False})
    assert res.get_json()['active'] is False
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert log['detail']['changes'] == {'name': ['Interessent', 'Bewerber'], 'active': [True, False]}


def test_unbekannte_liste_und_kein_loeschen(as_user):
    admin = as_user('root_admin')
    assert admin.get('/api/catalogs/geheim').status_code == 404
    assert admin.delete('/api/catalogs/language-level/1').status_code == 405

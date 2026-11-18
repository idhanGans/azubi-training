"""Kurse: Anlegen, Dozent/Modul zuordnen (mit Querpruefungen), Teilnehmer, Archiv."""
import pytest


@pytest.fixture
def setup(as_user):
    """B1- und A2-Curriculum mit je einem Modul, Dozentin fuer B1."""
    admin = as_user('root_admin')
    lv = {e['code']: e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries']}
    pid = admin.post('/api/programs', json={'name': 'Deutschsprachkurs'}).get_json()['id']
    modules = {}
    for code in ('B1', 'A2'):
        cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': lv[code]}).get_json()['id']
        modules[code] = admin.post(f'/api/curricula/{cur}/modules', json={'name': f'Modul {code}'}).get_json()['id']
    maria = admin.post('/api/instructors', json={'name': 'Maria Weber', 'msh_user': 'maria',
                                                 'level_ids': [lv['B1']]}).get_json()['id']
    return {'admin': admin, 'lv': lv, 'modules': modules, 'maria': maria}


def _course(s, **extra):
    return s['admin'].post('/api/courses', json={'name': 'B1 – Gruppe Herbst', 'level_id': s['lv']['B1'], **extra})


def test_kurs_mit_modul_und_dozent(setup):
    res = _course(setup, module_id=setup['modules']['B1'], instructor_id=setup['maria'], status='RUNNING')
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body['module']['name'] == 'Modul B1' and body['module']['program'] == 'Deutschsprachkurs'
    assert body['instructor']['name'] == 'Maria Weber'
    listing = setup['admin'].get('/api/courses').get_json()['courses']
    assert [c['participant_count'] for c in listing] == [0]
    assert setup['admin'].get(f'/api/courses?instructor_id={setup["maria"]}').get_json()['courses']
    assert setup['admin'].get(f'/api/courses?level_id={setup["lv"]["A2"]}').get_json()['courses'] == []
    assert setup['admin'].get('/api/courses?status=FERTIG').status_code == 400


def test_zuordnungs_konflikte(setup):
    admin = setup['admin']
    res = _course(setup, module_id=setup['modules']['A2'])
    assert res.status_code == 409 and res.get_json()['field'] == 'module_id'
    res = _course(setup, level_id=setup['lv']['A2'], instructor_id=setup['maria'])
    assert res.status_code == 409 and 'unterrichtet das Sprachniveau A2 nicht' in res.get_json()['error']
    admin.patch(f'/api/instructors/{setup["maria"]}', json={'status': 'ON_LEAVE'})
    res = _course(setup, instructor_id=setup['maria'])
    assert res.status_code == 409 and 'nicht aktiv' in res.get_json()['error']
    assert _course(setup).status_code == 201
    assert _course(setup, name='b1 – gruppe herbst').status_code == 409      # Name schon vergeben


def test_niveauwechsel_prueft_modul_und_dozent_erneut(setup):
    admin = setup['admin']
    cid = _course(setup, module_id=setup['modules']['B1'], instructor_id=setup['maria']).get_json()['id']
    res = admin.patch(f'/api/courses/{cid}', json={'level_id': setup['lv']['A2']})
    assert res.status_code == 409 and res.get_json()['field'] == 'module_id'
    res = admin.patch(f'/api/courses/{cid}', json={'level_id': setup['lv']['A2'], 'module_id': setup['modules']['A2']})
    assert res.status_code == 409 and res.get_json()['field'] == 'instructor_id'
    ok = admin.patch(f'/api/courses/{cid}', json={'level_id': setup['lv']['A2'], 'module_id': setup['modules']['A2'],
                                                  'instructor_id': None})
    assert ok.status_code == 200 and ok.get_json()['instructor'] is None
    # ein spaeter inaktiver Dozent blockiert nicht das Bearbeiten anderer Felder
    cid2 = _course(setup, name='B1 Zwei', instructor_id=setup['maria']).get_json()['id']
    admin.patch(f'/api/instructors/{setup["maria"]}', json={'status': 'INACTIVE'})
    assert admin.patch(f'/api/courses/{cid2}', json={'description': 'Neu'}).status_code == 200


def test_dozentenwechsel_im_protokoll(setup):
    admin = setup['admin']
    cid = _course(setup).get_json()['id']
    admin.patch(f'/api/courses/{cid}', json={'instructor_id': setup['maria']})
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert log['summary'] == 'Dozent für B1 – Gruppe Herbst: Maria Weber'
    assert log['detail']['changes'] == {'instructor': [None, 'Maria Weber']}


def test_teilnehmer(setup, trainee):
    admin = setup['admin']
    cid = _course(setup).get_json()['id']
    budi, sari, alt = trainee('Budi'), trainee('Sari'), trainee('Alt')
    admin.post(f'/api/candidates/{alt}/archive')
    assert admin.post(f'/api/courses/{cid}/participants', json={'trainee_ids': [budi, alt]}).status_code == 400
    assert admin.post(f'/api/courses/{cid}/participants', json={'trainee_ids': []}).status_code == 400
    res = admin.post(f'/api/courses/{cid}/participants', json={'trainee_ids': [budi, sari]})
    assert res.get_json()['added'] == [budi, sari]
    assert admin.post(f'/api/courses/{cid}/participants', json={'trainee_ids': [budi]}).get_json()['added'] == []
    names = [p['name'] for p in admin.get(f'/api/courses/{cid}').get_json()['participants']]
    assert names == ['Budi', 'Sari']
    assert admin.get(f'/api/candidates/{budi}').get_json()['courses'][0]['name'] == 'B1 – Gruppe Herbst'
    assert admin.delete(f'/api/courses/{cid}/participants/{budi}').status_code == 200
    assert admin.delete(f'/api/courses/{cid}/participants/{budi}').status_code == 404
    assert admin.get('/api/activity').get_json()['activity'][0]['summary'] == 'Aus B1 – Gruppe Herbst entfernt: Budi'


def test_archivieren_und_namensgleichheit(setup):
    admin = setup['admin']
    cid = _course(setup).get_json()['id']
    admin.post(f'/api/courses/{cid}/archive')
    assert admin.get('/api/courses').get_json()['courses'] == []
    assert _course(setup).status_code == 201                        # Name wieder frei
    assert admin.post(f'/api/courses/{cid}/restore').status_code == 409


@pytest.mark.parametrize('role,anlegen', [
    ('ACADEMIC_MANAGER', 201), ('HR', 403), ('MANAGEMENT', 403), ('INSTRUCTOR', 403),
])
def test_rechte(setup, as_user, grant, role, anlegen):
    grant('person', role)
    res = as_user('person').post('/api/courses', json={'name': 'X', 'level_id': setup['lv']['B1']})
    assert res.status_code == anlegen


def test_module_je_niveau(setup):
    mods = setup['admin'].get(f'/api/modules?level_id={setup["lv"]["B1"]}').get_json()['modules']
    assert [m['name'] for m in mods] == ['Modul B1']
    assert setup['admin'].get('/api/modules').status_code == 400

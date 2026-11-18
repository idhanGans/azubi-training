"""Authentifizierung: ohne gueltiges Token kommt niemand an Daten — auch nicht
mit einem selbst gesetzten X-Auth-User-Header (cluster-intern faelschbar)."""


def test_api_ohne_token_ist_401(as_user):
    assert as_user(None).get('/api/trainees').status_code == 401


def test_browser_ohne_token_wird_zum_login_umgeleitet(app, db):
    res = app.test_client().get('/training', headers={'Accept': 'text/html'})
    assert res.status_code == 302
    assert res.headers['Location'].startswith('https://login.example/login')


def test_gefaelschter_x_auth_user_header_zaehlt_nicht(as_user, grant):
    grant('root_boss', 'SUPER_ADMIN')
    res = as_user(None).get('/api/trainees', headers={'X-Auth-User': 'root_boss'})
    assert res.status_code == 401


def test_ungueltiges_token_ist_401(as_user):
    assert as_user('kaputt').get('/api/me').status_code == 401


def test_health_und_docs_ohne_token(app, db):
    client = app.test_client()
    assert client.get('/health').status_code == 200
    assert client.get('/docs').status_code == 200


def test_identitaet_kommt_aus_dem_token(as_user):
    body = as_user('Root_Admin').get('/api/me').get_json()
    assert body['user'] == 'root_admin'
    assert body['roles'] == ['SUPER_ADMIN']


def test_schreiben_ohne_json_wird_abgelehnt_csrf(app, db, trainee):
    """Ein Formular-POST einer fremden Seite (text/plain) darf nichts aendern."""
    tid = trainee('Anna')
    res = app.test_client().post(f'/api/candidates/{tid}/archive', data='x',
                                 headers={'Authorization': 'Bearer root_admin', 'Content-Type': 'text/plain'})
    assert res.status_code == 415
    from app.models.trainee import Trainee
    assert db.session.get(Trainee, tid).archived_at is None

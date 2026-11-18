"""Kandidat: sieht und bearbeitet nur den eigenen Report — Kandidat A nie Kandidat B."""
from datetime import timedelta

from app.models.common import utcnow
from app.models.training_report import TrainingReport


def _report(client, **extra):
    return client.post('/api/training/me', json={'period': '2026-09-20', 'hours': 6,
                                                 'lang': True, 'learned': 'Konjunktiv II', **extra})


def test_kandidat_legt_eigenen_report_an_und_sieht_nur_den(as_user, trainee):
    trainee('Anna', msh_user='anna')
    trainee('Budi', msh_user='budi')
    assert _report(as_user('anna')).status_code == 201
    assert _report(as_user('budi'), learned='Perfekt').status_code == 201
    reports = as_user('anna').get('/api/training/me').get_json()['reports']
    assert [r['learned'] for r in reports] == ['Konjunktiv II']


def test_kandidat_kann_fremden_report_nicht_aendern(as_user, trainee):
    trainee('Anna', msh_user='anna')
    trainee('Budi', msh_user='budi')
    rid = _report(as_user('budi')).get_json()['id']
    res = as_user('anna').put(f'/api/training/me/{rid}', json={'hours': 1, 'learned': 'x'})
    assert res.status_code == 404


def test_kandidat_kommt_nicht_an_team_daten(as_user, trainee):
    trainee('Anna', msh_user='anna')
    client = as_user('anna')
    for url in ('/api/trainees', '/api/training', '/api/ratings', '/api/activity', '/api/users'):
        assert client.get(url).status_code == 403, url
    assert client.get('/training', headers={'Accept': 'text/html'}).status_code == 403


def test_kandidat_wird_auf_sein_portal_geleitet(as_user, trainee):
    trainee('Anna', msh_user='anna')
    res = as_user('anna').get('/', headers={'Accept': 'text/html'})
    assert res.status_code == 302 and res.headers['Location'].endswith('/my')


def test_report_nach_7_tagen_gesperrt(as_user, trainee, db):
    trainee('Anna', msh_user='anna')
    rid = _report(as_user('anna')).get_json()['id']
    db.session.get(TrainingReport, rid).created_at = utcnow() - timedelta(days=8)
    db.session.commit()
    res = as_user('anna').put(f'/api/training/me/{rid}', json={'hours': 2})
    assert res.status_code == 403


def test_bearbeitung_wird_mit_alt_und_neu_protokolliert(as_user, trainee, grant):
    trainee('Anna', msh_user='anna')
    rid = _report(as_user('anna')).get_json()['id']
    res = as_user('anna').put(f'/api/training/me/{rid}', json={'period': '2026-09-20', 'hours': 7,
                                                               'lang': True, 'learned': 'Konjunktiv II'})
    assert res.status_code == 200
    log = as_user('root_admin').get('/api/activity').get_json()['activity']
    assert log[0]['action'] == 'report.update'
    assert log[0]['detail']['changes']['hours'] == [6.0, 7.0]


def test_ungueltige_stunden_werden_abgelehnt(as_user, trainee):
    trainee('Anna', msh_user='anna')
    res = _report(as_user('anna'), hours=30)
    assert res.status_code == 400
    assert res.get_json() == {'error': 'Der Wert für „Trainingsstunden“ muss zwischen 0 und 24 liegen.',
                              'field': 'hours'}


def test_leerer_report_wird_abgelehnt(as_user, trainee):
    trainee('Anna', msh_user='anna')
    res = as_user('anna').post('/api/training/me', json={'period': '2026-09-20'})
    assert res.status_code == 400


def test_summe_der_reports_kommt_vom_server(as_user, trainee):
    """Kandidat und Team sehen dieselbe Summe aus derselben Stelle (training_stats.report_summary)."""
    tid = trainee('Anna', msh_user='anna')
    anna = as_user('anna')
    _report(anna)
    _report(anna, period='2026-09-21', hours=2.5)
    assert anna.get('/api/training/me').get_json()['summary'] == {'report_count': 2, 'hours_total': 8.5}
    team = as_user('root_admin').get(f'/api/candidates/{tid}').get_json()['training']
    assert (team['report_count'], team['hours_total']) == (2, 8.5)

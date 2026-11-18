"""Benachrichtigungen: Ereignisse, faellige Erinnerungen (ohne Doppelte), Erledigen, nur eigene."""
from datetime import timedelta

import pytest

from app.models.common import utcnow
from app.services.local_time import today


def _day(days):
    return (today() + timedelta(days=days)).isoformat()


@pytest.fixture
def nt(as_user, grant, trainee):
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    maria = admin.post('/api/instructors', json={'name': 'Maria', 'msh_user': 'maria', 'level_ids': [b1]}).get_json()['id']
    grant('maria', 'INSTRUCTOR')
    budi, sari = trainee('Budi', msh_user='budi'), trainee('Sari', msh_user='sari')
    ohne_login = trainee('Ohne Login')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'instructor_id': maria}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi, ohne_login]})

    def session(days, start='10:00', end='12:00'):
        return admin.post('/api/sessions', json={'course_id': k1, 'date': _day(days), 'start': start, 'end': end,
                                                 'room': 'R 1'}).get_json()['sessions'][0]['id']
    tpl = admin.post('/api/assessment-templates', json={'name': 'Monat', 'passing_percent': 60, 'categories': [
        {'name': 'Sprechen', 'max_score': 10, 'weight': 1}]}).get_json()
    return {'admin': admin, 'budi': as_user('budi'), 'sari': as_user('sari'), 'maria': as_user('maria'),
            'budi_id': budi, 'sari_id': sari, 'k1': k1, 'maria_id': maria, 'session': session, 'tpl': tpl}


def _list(client, **kw):
    return client.get('/api/notifications' + ('?unread=1' if kw.get('unread') else '')).get_json()


def _types(client):
    return [n['type'] for n in _list(client)['notifications']]


def test_aufnahme_in_kurs(nt):
    items = _list(nt['budi'])['notifications']
    assert [(n['type'], n['params'], n['link']) for n in items] == [('COURSE_JOINED', {'course': 'Kurs Maria'}, '/my-course')]
    assert _types(nt['sari']) == []


def test_erinnerung_morgen_einmal_fuer_kandidat_und_dozent(nt):
    nt['session'](1)
    nt['session'](2, start='14:00', end='15:00')                  # uebermorgen: noch nicht
    for _ in range(3):
        nt['budi'].get('/api/notifications/count')
    reminders = [n for n in _list(nt['budi'])['notifications'] if n['type'] == 'SESSION_REMINDER']
    assert len(reminders) == 1
    assert reminders[0]['params'] == {'course': 'Kurs Maria', 'date': _day(1), 'start': '10:00', 'end': '12:00',
                                      'room': 'R 1'}
    maria = _list(nt['maria'])['notifications']
    assert [n['type'] for n in maria] == ['SESSION_REMINDER'] and maria[0]['link'] == f'/schedule?view=day&date={_day(1)}'


def test_absage_und_verschiebung(nt):
    sid = nt['session'](1)
    nt['budi'].get('/api/notifications/count')                     # Erinnerung entsteht
    nt['admin'].patch(f'/api/sessions/{sid}', json={'date': _day(3), 'start': '09:00', 'end': '11:00'})
    moved = next(n for n in _list(nt['budi'])['notifications'] if n['type'] == 'SESSION_MOVED')
    assert (moved['params']['old_date'], moved['params']['old_start'], moved['params']['date'],
            moved['params']['start']) == (_day(1), '10:00', _day(3), '09:00')
    reminder = next(n for n in _list(nt['budi'])['notifications'] if n['type'] == 'SESSION_REMINDER')
    assert reminder['read'] is True                                 # alte Erinnerung erledigt
    nt['admin'].patch(f'/api/sessions/{sid}', json={'status': 'CANCELLED', 'cancel_reason': 'Dozentin krank'})
    cancelled = next(n for n in _list(nt['maria'])['notifications'] if n['type'] == 'SESSION_CANCELLED')
    assert cancelled['params']['reason'] == 'Dozentin krank'
    assert 'SESSION_CANCELLED' in _types(nt['budi']) and _types(nt['sari']) == []


def test_vergangene_termine_melden_nichts(nt):
    sid = nt['session'](-3)
    nt['admin'].patch(f'/api/sessions/{sid}', json={'start': '11:00', 'end': '12:00'})
    assert 'SESSION_MOVED' not in _types(nt['budi'])


def test_bewertung_veroeffentlicht_korrigiert_und_entwurf_erinnerung(nt, db):
    from app.models.assessment import Assessment
    tpl, cat = nt['tpl'], nt['tpl']['categories'][0]['id']
    aid = nt['admin'].post('/api/assessments', json={
        'trainee_id': nt['budi_id'], 'template_id': tpl['id'], 'instructor_id': nt['maria_id'],
        'assessed_on': _day(-1), 'scores': [{'category_id': cat, 'points': 7}]}).get_json()['assessment']['id']
    assert 'ASSESSMENT_DRAFT_OPEN' not in _types(nt['maria'])       # erst nach 3 Tagen
    db.session.get(Assessment, aid).created_at = utcnow() - timedelta(days=4)
    db.session.commit()
    draft = next(n for n in _list(nt['maria'])['notifications'] if n['type'] == 'ASSESSMENT_DRAFT_OPEN')
    assert draft['params']['candidate'] == 'Budi' and draft['link'] == f'/assessments/{aid}'
    assert 'ASSESSMENT_PUBLISHED' not in _types(nt['budi'])        # Entwurf: Kandidat erfaehrt nichts
    nt['admin'].post(f'/api/assessments/{aid}/finalize')
    assert next(n for n in _list(nt['maria'])['notifications'] if n['type'] == 'ASSESSMENT_DRAFT_OPEN')['read']
    published = next(n for n in _list(nt['budi'])['notifications'] if n['type'] == 'ASSESSMENT_PUBLISHED')
    assert published['params'] == {'template': 'Monat', 'date': _day(-1)} and published['link'] == '/my-assessments'
    nt['admin'].patch(f'/api/assessments/{aid}', json={'scores': [{'category_id': cat, 'points': 8}], 'reason': 'Nachgezählt'})
    assert 'ASSESSMENT_CORRECTED' in _types(nt['budi'])


def test_anwesenheit_offen_bis_erfasst(nt):
    sid = nt['session'](-1)
    missing = next(n for n in _list(nt['maria'])['notifications'] if n['type'] == 'ATTENDANCE_MISSING')
    assert missing['params']['date'] == _day(-1)
    budi, ohne = nt['budi_id'], next(t for t in nt['admin'].get('/api/candidates').get_json()['items']
                                     if t['name'] == 'Ohne Login')['id']
    nt['admin'].put(f'/api/sessions/{sid}/attendance', json={'entries': [{'trainee_id': budi, 'status': 'PRESENT'}]})
    assert not next(n for n in _list(nt['maria'])['notifications'] if n['type'] == 'ATTENDANCE_MISSING')['read']
    nt['admin'].put(f'/api/sessions/{sid}/attendance', json={'entries': [{'trainee_id': ohne, 'status': 'PRESENT'}]})
    assert next(n for n in _list(nt['maria'])['notifications'] if n['type'] == 'ATTENDANCE_MISSING')['read']


def test_nur_eigene_lesen_und_markieren(nt, as_user):
    own = _list(nt['budi'])
    assert own['unread'] == 1
    nid = own['notifications'][0]['id']
    assert nt['sari'].post(f'/api/notifications/{nid}/read').status_code == 404
    assert _list(nt['budi'])['unread'] == 1
    assert nt['budi'].post(f'/api/notifications/{nid}/read').get_json() == {'unread': 0}
    assert nt['budi'].post(f'/api/notifications/{nid}/read').status_code == 200    # doppelt: kein Fehler
    assert _list(nt['budi'], unread=True)['notifications'] == []
    nt['session'](1)
    assert nt['budi'].get('/api/notifications/count').get_json() == {'unread': 1}   # Erinnerung beim Oeffnen
    assert nt['budi'].post('/api/notifications/read-all').get_json()['marked'] == 1
    assert as_user('niemand').get('/api/notifications/count').get_json() == {'unread': 0}


def test_glocke_und_seiten(nt, as_user, grant):
    html = nt['budi'].get('/my', headers={'Accept': 'text/html'}).get_data(as_text=True)
    assert 'class="bell" href="/my-notifications"' in html and 'href="/my-notifications"' in html
    assert nt['maria'].get('/notifications', headers={'Accept': 'text/html'}).status_code == 200
    assert 'class="bell" href="/notifications"' in nt['maria'].get('/teaching', headers={'Accept': 'text/html'}).get_data(as_text=True)
    assert nt['maria'].get('/my-notifications', headers={'Accept': 'text/html'}).status_code == 403

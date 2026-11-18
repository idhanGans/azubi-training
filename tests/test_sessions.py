"""Schedule: sessions, local time/UTC, time conflicts (instructor + candidate), rescheduling, cancelling, permissions."""
import re
from datetime import date, timedelta

import pytest

from app.services.local_time import today


def _monday(weeks_ahead=1):
    day = today() + timedelta(weeks=weeks_ahead)
    return day - timedelta(days=day.weekday())


@pytest.fixture
def plan(as_user, trainee):
    """Two B1 courses: "Kurs Maria" (Budi, Sari) and "Kurs Tom" (Dewi); Maria is available Mon 08–16."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    pid = admin.post('/api/programs', json={'name': 'Deutschsprachkurs'}).get_json()['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    module = admin.post(f'/api/curricula/{cur}/modules', json={'name': 'Modul 8'}).get_json()['id']
    maria = admin.post('/api/instructors', json={'name': 'Maria', 'msh_user': 'maria', 'level_ids': [b1],
                                                 'availability': [{'weekday': 0, 'start': '08:00', 'end': '16:00'}]}
                       ).get_json()['id']
    tom = admin.post('/api/instructors', json={'name': 'Tom', 'msh_user': 'tom', 'level_ids': [b1]}).get_json()['id']
    budi, sari, dewi = trainee('Budi', msh_user='budi'), trainee('Sari'), trainee('Dewi', msh_user='dewi')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'module_id': module,
                                          'instructor_id': maria}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1, 'instructor_id': tom}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi, sari]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})
    return {'admin': admin, 'b1': b1, 'module': module, 'maria': maria, 'tom': tom, 'budi': budi, 'sari': sari,
            'dewi': dewi, 'k1': k1, 'k2': k2, 'mon': _monday().isoformat()}


def _add(plan, course, start='10:00', end='12:00', **extra):
    return plan['admin'].post('/api/sessions', json={'course_id': plan[course], 'date': extra.pop('date', plan['mon']),
                                                     'start': start, 'end': end, **extra})


def test_termin_in_ortszeit_mit_vorgaben_vom_kurs(plan):
    res = _add(plan, 'k1', room='R 2.14', online_url='https://meet.example/b1')
    assert res.status_code == 201, res.get_json()
    s = res.get_json()['sessions'][0]
    assert (s['date'], s['start'], s['end'], s['duration_minutes']) == (plan['mon'], '10:00', '12:00', 120)
    assert s['instructor']['name'] == 'Maria' and s['module']['name'] == 'Modul 8'
    assert res.get_json()['warnings'] == []


def test_sommer_und_winterzeit(plan):
    year = today().year + 1
    summer = _add(plan, 'k1', date=date(year, 7, 13).isoformat()).get_json()['sessions'][0]
    winter = _add(plan, 'k1', date=date(year, 1, 12).isoformat()).get_json()['sessions'][0]
    assert summer['starts_at'].startswith(f'{year}-07-13T08:00:00')     # 10:00 CEST = 08:00 UTC
    assert winter['starts_at'].startswith(f'{year}-01-12T09:00:00')     # 10:00 CET = 09:00 UTC
    assert summer['start'] == winter['start'] == '10:00'


def test_dozent_doppelt_eingeplant(plan):
    assert _add(plan, 'k1').status_code == 201
    plan['admin'].patch(f'/api/courses/{plan["k2"]}', json={'instructor_id': plan['maria']})
    res = _add(plan, 'k2', start='11:00', end='13:00')
    assert res.status_code == 409
    body = res.get_json()
    assert body['error'].startswith('Zeitkonflikt erkannt. Der Dozent ist zu diesem Zeitpunkt bereits eingeplant.')
    assert body['details']['kind'] == 'instructor' and body['details']['sessions'][0]['course'] == 'Kurs Maria'
    assert _add(plan, 'k2', start='12:00', end='13:00').status_code == 201     # directly following: ok


def test_kandidat_doppelt_eingeplant(plan):
    assert _add(plan, 'k1').status_code == 201
    plan['admin'].post(f'/api/courses/{plan["k2"]}/participants', json={'trainee_ids': [plan['budi']]})  # still free
    res = _add(plan, 'k2', start='11:30', end='12:30')
    assert res.status_code == 409
    assert res.get_json()['error'].startswith('Zeitkonflikt erkannt. Budi ist zu diesem Zeitpunkt bereits eingeplant')
    assert res.get_json()['details']['candidates'][0]['name'] == 'Budi'


def test_neuer_teilnehmer_mit_konflikt(plan):
    _add(plan, 'k1')
    _add(plan, 'k2', start='11:00', end='12:00')
    res = plan['admin'].post(f'/api/courses/{plan["k2"]}/participants', json={'trainee_ids': [plan['sari']]})
    assert res.status_code == 409 and 'Sari ist' in res.get_json()['error']
    names = [p['name'] for p in plan['admin'].get(f'/api/courses/{plan["k2"]}').get_json()['participants']]
    assert names == ['Dewi']                                      # nothing half-saved


def test_woechentliche_serie_ganz_oder_gar_nicht(plan):
    third = (date.fromisoformat(plan['mon']) + timedelta(weeks=2)).isoformat()
    _add(plan, 'k2', date=third)                                  # Tom, only Dewi
    plan['admin'].post(f'/api/courses/{plan["k2"]}/participants', json={'trainee_ids': [plan['budi']]})
    until = (date.fromisoformat(plan['mon']) + timedelta(weeks=3)).isoformat()
    res = _add(plan, 'k1', repeat_until=until)
    assert res.status_code == 409 and res.get_json()['details']['candidates'][0]['date'] == third
    assert plan['admin'].get(f'/api/sessions?from={plan["mon"]}&to={until}&course_id={plan["k1"]}') \
        .get_json()['sessions'] == []
    plan['admin'].delete(f'/api/courses/{plan["k2"]}/participants/{plan["budi"]}')
    created = _add(plan, 'k1', repeat_until=until).get_json()['sessions']
    assert [s['date'] for s in created] == [(date.fromisoformat(plan['mon']) + timedelta(weeks=i)).isoformat()
                                            for i in range(4)]


def test_verschieben_und_absagen(plan):
    admin = plan['admin']
    sid = _add(plan, 'k1').get_json()['sessions'][0]['id']
    blocker = _add(plan, 'k1', start='14:00', end='15:00').get_json()['sessions'][0]['id']
    assert admin.patch(f'/api/sessions/{sid}', json={'start': '14:30', 'end': '15:30'}).status_code == 409
    res = admin.patch(f'/api/sessions/{sid}', json={'start': '09:00', 'end': '11:00'})
    assert res.status_code == 200
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert log['summary'] == 'Termin verschoben: Kurs Maria'
    assert log['detail']['changes']['start'] == ['10:00', '09:00']
    assert admin.patch(f'/api/sessions/{blocker}', json={'status': 'CANCELLED'}).status_code == 400   # reason missing
    assert admin.patch(f'/api/sessions/{blocker}', json={'status': 'CANCELLED', 'cancel_reason': 'Dozentin krank'}
                       ).get_json()['session']['cancel_reason'] == 'Dozentin krank'
    assert admin.patch(f'/api/sessions/{sid}', json={'start': '14:00', 'end': '15:00'}).status_code == 200  # free
    res = admin.patch(f'/api/sessions/{blocker}', json={'status': 'SCHEDULED'})
    assert res.status_code == 409                               # reactivating checks again
    listed = admin.get(f'/api/sessions?from={plan["mon"]}&to={plan["mon"]}').get_json()['sessions']
    assert [s['id'] for s in listed] == [sid]
    with_cancelled = admin.get(f'/api/sessions?from={plan["mon"]}&to={plan["mon"]}&include_cancelled=1')
    assert len(with_cancelled.get_json()['sessions']) == 2


def test_vertretung_muss_niveau_unterrichten(plan):
    admin = plan['admin']
    a2 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'A2')
    ina = admin.post('/api/instructors', json={'name': 'Ina', 'level_ids': [a2]}).get_json()['id']
    sid = _add(plan, 'k1').get_json()['sessions'][0]['id']
    res = admin.patch(f'/api/sessions/{sid}', json={'instructor_id': ina})
    assert res.status_code == 409 and 'unterrichtet das Sprachniveau B1 nicht' in res.get_json()['error']
    res = admin.patch(f'/api/sessions/{sid}', json={'instructor_id': plan['tom']})
    assert res.get_json()['session']['instructor']['name'] == 'Tom'


def test_verfuegbarkeit_nur_als_hinweis(plan):
    res = _add(plan, 'k1', start='17:00', end='18:30')
    assert res.status_code == 201
    assert res.get_json()['warnings'] == [
        f'Außerhalb der Verfügbarkeit von Maria: {date.fromisoformat(plan["mon"]).strftime("%d.%m.%Y")} 17:00–18:30 Uhr.']


@pytest.mark.parametrize('extra,feld', [
    ({'start': '12:00', 'end': '10:00'}, 'end'),
    ({'start': '07:00', 'end': '18:00'}, 'end'),
    ({'start': '9 Uhr'}, 'start'),
    ({'online_url': 'javascript:alert(1)'}, 'online_url'),
    ({'date': '2020-01-01'}, 'date'),
    ({'repeat_until': '2020-01-01'}, 'repeat_until'),
])
def test_ungueltige_eingaben(plan, extra, feld):
    res = _add(plan, 'k1', **extra)
    assert res.status_code == 400 and res.get_json()['field'] == feld


def test_serie_hoechstens_52(plan):
    until = (date.fromisoformat(plan['mon']) + timedelta(weeks=60)).isoformat()
    res = _add(plan, 'k1', repeat_until=until)
    assert res.status_code == 400 and res.get_json()['field'] == 'repeat_until'


def test_kalender_filter_und_zeitraum(plan):
    _add(plan, 'k1')
    _add(plan, 'k2', start='14:00', end='15:00')
    admin, mon = plan['admin'], plan['mon']
    q = f'/api/sessions?from={mon}&to={mon}'
    assert len(admin.get(q).get_json()['sessions']) == 2
    assert [s['course']['name'] for s in admin.get(q + f'&trainee_id={plan["dewi"]}').get_json()['sessions']] == ['Kurs Tom']
    assert [s['course']['name'] for s in admin.get(q + f'&instructor_id={plan["maria"]}').get_json()['sessions']] == ['Kurs Maria']
    assert [s['course']['name'] for s in admin.get(q + f'&module_id={plan["module"]}').get_json()['sessions']] == ['Kurs Maria']
    assert admin.get(q + f'&level_id={plan["b1"]}').get_json()['sessions'][0]['participant_count'] == 2
    far = (date.fromisoformat(mon) + timedelta(days=70)).isoformat()
    assert admin.get(f'/api/sessions?from={mon}&to={far}').status_code == 400
    assert admin.get('/api/sessions').status_code == 400


def test_dozent_sieht_nur_eigene_termine(plan, as_user, grant):
    _add(plan, 'k1')
    _add(plan, 'k2', start='14:00', end='15:00')
    grant('maria', 'INSTRUCTOR')
    maria = as_user('maria')
    listed = maria.get(f'/api/sessions?from={plan["mon"]}&to={plan["mon"]}').get_json()['sessions']
    assert [s['course']['name'] for s in listed] == ['Kurs Maria']
    other = plan['admin'].get(f'/api/sessions?from={plan["mon"]}&to={plan["mon"]}&course_id={plan["k2"]}')
    assert maria.get(f'/api/sessions/{other.get_json()["sessions"][0]["id"]}').status_code == 404
    assert maria.post('/api/sessions', json={'course_id': plan['k1']}).status_code == 403


def test_vertretung_sieht_kurs_und_teilnehmer(plan, as_user, grant):
    sid = _add(plan, 'k1').get_json()['sessions'][0]['id']
    plan['admin'].patch(f'/api/sessions/{sid}', json={'instructor_id': plan['tom']})
    grant('tom', 'INSTRUCTOR')
    tom = as_user('tom')
    assert tom.get(f'/api/courses/{plan["k1"]}').status_code == 200
    assert {c['name'] for c in tom.get('/api/candidates').get_json()['items']} == {'Budi', 'Sari', 'Dewi'}
    plan['admin'].patch(f'/api/sessions/{sid}', json={'status': 'CANCELLED', 'cancel_reason': 'entfällt'})
    assert tom.get(f'/api/courses/{plan["k1"]}').status_code == 404      # cancelled substitution doesn't count


def test_kandidat_sieht_nur_eigenen_stundenplan(plan, as_user):
    _add(plan, 'k1', notes='intern: Budi braucht Förderung')
    _add(plan, 'k2', start='14:00', end='15:00')
    budi = as_user('budi')
    mine = budi.get(f'/api/my-schedule?from={plan["mon"]}&to={plan["mon"]}').get_json()['sessions']
    assert [s['course']['name'] for s in mine] == ['Kurs Maria']
    assert 'notes' not in mine[0] and 'created_by' not in mine[0]
    assert len(budi.get('/api/my-schedule').get_json()['sessions']) == 1          # default: 4 weeks from today
    assert budi.get(f'/api/sessions?from={plan["mon"]}&to={plan["mon"]}').status_code == 403
    assert as_user('maria').get('/api/my-schedule').status_code == 403           # not a candidate


@pytest.mark.parametrize('role,anlegen', [('ACADEMIC_MANAGER', 201), ('HR', 403), ('MANAGEMENT', 403)])
def test_rechte(plan, as_user, grant, role, anlegen):
    grant('person', role)
    res = as_user('person').post('/api/sessions', json={'course_id': plan['k1'], 'date': plan['mon'],
                                                        'start': '10:00', 'end': '11:00'})
    assert res.status_code == anlegen


def test_mein_unterricht_mit_terminen(plan, as_user):
    day = today()
    plan['admin'].post('/api/sessions', json={'course_id': plan['k1'], 'date': day.isoformat(),
                                              'start': '00:00', 'end': '01:30'})
    plan['admin'].post('/api/sessions', json={'course_id': plan['k1'], 'date': (day + timedelta(days=3)).isoformat(),
                                              'start': '10:00', 'end': '12:00'})
    body = as_user('maria').get('/api/my-teaching').get_json()
    assert body['stats']['today_count'] == 1 and len(body['upcoming']) == 1
    same_month = (day + timedelta(days=3)).month == day.month
    assert body['stats']['hours_month'] == (3.5 if same_month else 1.5)


def test_archivierter_kurs_nimmt_keine_termine(plan):
    plan['admin'].post(f'/api/courses/{plan["k1"]}/archive')
    res = _add(plan, 'k1')
    assert res.status_code == 400 and res.get_json()['field'] == 'course_id'


def test_profil_zeigt_naechste_termine(plan):
    _add(plan, 'k1')
    body = plan['admin'].get(f'/api/candidates/{plan["budi"]}').get_json()
    assert [s['course']['name'] for s in body['upcoming_sessions']] == ['Kurs Maria']


def test_serie_ueber_zeitumstellung_bleibt_ortszeit(plan):
    """Weekly series across the end of daylight saving time: every week 10:00 local time, in UTC first 08:00, then 09:00."""
    year = today().year + 1
    dst_end = max(date(year, 10, d) for d in range(25, 32) if date(year, 10, d).weekday() == 6)
    first = dst_end - timedelta(days=6)                                     # Monday before
    res = _add(plan, 'k1', date=first.isoformat(), repeat_until=(first + timedelta(weeks=2)).isoformat())
    sessions = res.get_json()['sessions']
    assert [s['start'] for s in sessions] == ['10:00'] * 3
    assert [s['starts_at'][11:13] for s in sessions] == ['08', '09', '09']
    assert [s['duration_minutes'] for s in sessions] == [120] * 3


def test_spaeter_termin_gehoert_zum_ortstag(plan):
    """23:00 local time is still the same day in UTC, but 00:30 is the previous day — what counts is the local day."""
    day = date.fromisoformat(plan['mon'])
    _add(plan, 'k2', start='23:00', end='23:45')
    _add(plan, 'k2', date=(day + timedelta(days=1)).isoformat(), start='00:30', end='01:15')
    listed = lambda d: [(s['date'], s['start']) for s in plan['admin'].get(
        f'/api/sessions?from={d.isoformat()}&to={d.isoformat()}').get_json()['sessions']]
    assert listed(day) == [(plan['mon'], '23:00')]
    assert listed(day + timedelta(days=1)) == [((day + timedelta(days=1)).isoformat(), '00:30')]


def test_verlauf_und_hinweise_mit_deutschem_datum(plan):
    _add(plan, 'k1')
    entry = plan['admin'].get('/api/activity?action=session.create').get_json()['activity'][0]
    de = date.fromisoformat(plan['mon']).strftime('%d.%m.%Y')
    assert entry['summary'] == f'Termin angelegt: Kurs Maria, {de}, 10:00–12:00 Uhr'
    conflict = _add(plan, 'k1', start='11:00', end='13:00').get_json()
    assert conflict['details']['sessions'][0]['text'] == f'Kurs Maria, {de}, 10:00–12:00 Uhr'


def test_seite_nennt_zeitzone_fuer_die_anzeige(plan):
    html = plan['admin'].get('/schedule', headers={'Accept': 'text/html'}).get_data(as_text=True)
    tag = re.search(r"<html [^>]*>", html).group(0)
    assert 'lang="de"' in tag and 'data-tz="Europe/Berlin"' in tag
    assert re.search(r'data-tz-label="(CEST|CET)"', tag)       # hint "Alle Uhrzeiten in …" names the real zone
    assert 'translate="no"' in tag           # own DE/EN/ID texts, no browser translator


def test_schul_zeitzone_aus_der_env():
    """The language course schedules in WIB (SCHOOL_TZ=Asia/Jakarta, no daylight saving time): 13–15 stays 06–08 UTC,
    even after the end of German daylight saving time. Separate process — TZ_NAME is read at import time."""
    import os
    import subprocess
    import sys
    code = ("from datetime import date; from app.services import local_time as lt; "
            "print(lt.TZ_NAME, lt.to_utc(date(2026, 10, 2), '13:00').isoformat(), "
            "lt.to_utc(date(2026, 10, 30), '13:00').isoformat(), lt.tz_label(), lt.local_parts(lt.to_utc(date(2026, 10, 30), '18:00')))")
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True,
                         env={**os.environ, 'SCHOOL_TZ': 'Asia/Jakarta'}).stdout.split(' ', 4)
    assert out[:4] == ['Asia/Jakarta', '2026-10-02T06:00:00+00:00', '2026-10-30T06:00:00+00:00', 'WIB']
    assert "('2026-10-30', '18:00')" in out[4]


def test_regeln_kommen_aus_dem_server(plan, as_user):
    """Numbers that are a business rule live only in the server — the frontend reads them from the API
    (attendance from 15 min before start, open attendance 14 days, upcoming 14 days, below 80%, threshold 60%)."""
    from datetime import datetime
    s = _add(plan, 'k1').get_json()['sessions'][0]
    assert (datetime.fromisoformat(s['starts_at']) - datetime.fromisoformat(s['attendance_from'])).seconds == 15 * 60
    teaching = as_user('maria').get('/api/my-teaching').get_json()
    assert teaching['windows'] == {'upcoming_days': 14, 'open_attendance_days': 14, 'open_lesson_days': 14}
    attention = plan['admin'].get('/api/dashboard').get_json()['attention']
    assert attention['open_attendance']['days'] == 14 and attention['low_attendance']['below_percent'] == 80
    assert plan['admin'].get('/api/assessment-templates').get_json()['default_passing_percent'] == 60

"""Modul-Bewertung nach der „Panduan Penilaian Deutschkurs": Punkte/Level, Erfassen der ganzen Gruppe samt
Anwesenheit, Regeln aus dem Leitfaden, mehrere Module je Termin, leere Felder, Reichweite, Auswertung je Gruppe,
Rueckmeldung fuer Kandidaten."""
from datetime import timedelta

import pytest

from app.services import lesson_scoring
from app.services.local_time import today


def _vals(v, r, w, f, p, pu, mi, ha):
    return dict(zip(('v', 'r', 'w', 'f', 'p', 'pu', 'mi', 'ha'), (v, r, w, f, p, pu, mi, ha)))


@pytest.mark.parametrize('values,total,level,capped', [
    (_vals(3, 2, 3, 2, 2, 1, 2, 1), 16, 'B', False),          # Beispiel Rina, Modul 3
    (_vals(3, 3, 3, 3, 1, 1, 2, 2), 18, 'C', True),           # Beispiel Budi: 18 Punkte, P nur 1 Stern -> C
    (_vals(3, 3, 3, 3, 2, 1, 2, 2), 19, 'A', False),
    (_vals(3, 3, 3, 3, 3, 1, 2, None), 20, 'A', False),       # keine Hausaufgabe = volle 2 Punkte
    (_vals(2, 2, 2, 2, 2, 1, 1, 1), 13, 'C', False),
    (_vals(2, 2, 2, 2, 2, 0, 0, 0), 10, 'D', False),
    (_vals(1, 1, 1, 1, 1, 0, 0, 0), 5, 'D', False),
    (_vals(3, 3, 3, 3, 2, 0, 1, 1), 16, 'B', False),
])
def test_punkte_und_level_wie_im_leitfaden(values, total, level, capped):
    result = lesson_scoring.evaluate(values)
    assert (result['total'], result['level'], result['capped']) == (total, level, capped)
    assert result['part_a'] + result['part_b'] == total


def test_regel_zahlen_fuer_die_oberflaeche():
    rules = lesson_scoring.rules()
    assert [(b['code'], b['min'], b['max']) for b in rules['levels']] == [
        ('A', 18, 20), ('B', 15, 17), ('C', 12, 14), ('D', 5, 11)]
    assert (rules['total_min'], rules['total_max']) == (5, 20)


@pytest.fixture
def lr(as_user, grant, trainee):
    """Gruppe Maria (Budi, Sari, Dewi) mit Modul 1/2, Gruppe Tom (Eka); Termine in der Vergangenheit."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    pid = admin.post('/api/programs', json={'name': 'Deutsch für Azubis'}).get_json()['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    m1, m2 = (admin.post(f'/api/curricula/{cur}/modules', json={'name': n}).get_json()['id']
              for n in ('Modul 1', 'Modul 2'))
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [b1]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    grant('hanna', 'HR')
    people = {n: trainee(n, msh_user=n.lower()) for n in ('Budi', 'Sari', 'Dewi', 'Eka')}
    k1 = admin.post('/api/courses', json={'name': 'Gruppe 1', 'level_id': b1, 'instructor_id': ids['maria'],
                                          'module_id': m1, 'status': 'RUNNING'}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Gruppe 2', 'level_id': b1, 'instructor_id': ids['tom'],
                                          'module_id': m1, 'status': 'RUNNING'}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [people['Budi'], people['Sari'], people['Dewi']]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [people['Eka']]})

    def session(course, days_ago, module, start='13:00'):
        day = (today() - timedelta(days=days_ago)).isoformat()
        res = admin.post('/api/sessions', json={'course_id': course, 'date': day, 'start': start, 'end': '15:00',
                                                'module_id': module})
        assert res.status_code == 201, res.get_json()
        return res.get_json()['sessions'][0]['id']

    s1, s2, s3 = session(k1, 6, m1), session(k1, 5, m1), session(k1, 4, m2)
    return {'admin': admin, 'maria': as_user('maria'), 'tom': as_user('tom'), 'hr': as_user('hanna'), **people,
            'k1': k1, 'k2': k2, 's1': s1, 's2': s2, 's3': s3, 'm1': m1, 'm2': m2, 'session': session,
            'budi': as_user('budi'), 'sari': as_user('sari')}


def _rating(tid, stars=(3, 2, 3, 2, 2), pu=1, mi=2, ha=1, strength='W', target='P', status='PRESENT', note=None):
    entry = dict(zip(('v', 'r', 'w', 'f', 'p'), stars))
    entry.update(trainee_id=tid, attendance=status, pu=pu, mi=mi, ha=ha, strength=strength, target=target, note=note)
    return entry


def _absent(tid, status='ABSENT', note=None):
    return {'trainee_id': tid, 'attendance': status, 'note': note}


def _put(client, sid, entries, homework_none=False, **sheet):
    return client.put(f'/api/sessions/{sid}/lesson-ratings',
                      json={'homework_none': homework_none, 'entries': entries, **sheet})


def test_ganze_gruppe_mit_anwesenheit_speichern(lr):
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi'], note='Fragt viel'),
                                       _rating(lr['Sari'], stars=(3, 3, 3, 3, 1), ha=2, strength='F', target='P'),
                                       _absent(lr['Dewi'], note='krank')])
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body['session']['status'] == 'COMPLETED' and body['session']['unit'] == 1
    assert body['summary'] == {'expected': 3, 'attended': 2, 'rated': 2}
    by_name = {e['trainee']['name']: e for e in body['entries']}
    assert by_name['Budi']['rating']['result'] == {'part_a': 12, 'part_b': 4, 'total': 16, 'level': 'B', 'capped': False,
                                                   'complete': True}
    assert by_name['Sari']['rating']['result']['level'] == 'C'                        # 18 Punkte, aber P = 1
    assert by_name['Dewi']['rating'] is None
    assert (by_name['Dewi']['attendance']['status'], by_name['Dewi']['attendance']['note']) == ('ABSENT', 'krank')
    log = lr['admin'].get('/api/activity?action=lesson_rating.record').get_json()['activity'][0]
    assert 'Modul 1 (Einheit 1)' in log['summary']
    assert log['detail']['changes']['Budi'] == [None, 'Modul 1 E1 · V3 R2 W3 F2 P2 · Pü1 Mi2 HA1 · 16 (B) · Stärke W · '
                                                      'Ziel P']
    assert log['detail']['attendance']['Dewi'] == [None, 'Abwesend']
    second = lr['maria'].get(f'/api/sessions/{lr["s2"]}/lesson-ratings').get_json()
    assert second['session']['unit'] == 2                                              # 2. Termin desselben Moduls
    assert second['sheet'] == {'module': {'id': lr['m1'], 'name': 'Modul 1'}, 'unit': 2}
    assert lr['maria'].get(f'/api/sessions/{lr["s3"]}/lesson-ratings').get_json()['session']['unit'] == 1


def test_ohne_hausaufgabe_zaehlt_ha_voll(lr):
    entries = [_rating(lr['Budi'], ha=None), _rating(lr['Sari'], ha=None), _absent(lr['Dewi'])]
    body = _put(lr['maria'], lr['s1'], entries, homework_none=True).get_json()
    assert body['homework_none'] is True
    assert body['entries'][0]['rating']['ha'] is None
    assert body['entries'][0]['rating']['result']['part_b'] == 5
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi'], ha=2), _rating(lr['Sari'], ha=None), _absent(lr['Dewi'])],
               homework_none=True)
    assert res.status_code == 400 and 'leer lassen' in res.get_json()['error']


@pytest.mark.parametrize('broken,message', [
    ({'p': 4}, 'zwischen 1 und 3'),
    ({'mi': 3}, 'zwischen 0 und 2'),
    ({'ha': None}, 'Hausaufgabe'),
    ({'strength': 'X'}, 'Stärke'),
    ({'target': ['P', 'Q']}, 'Ziel'),
    ({'attendance': 'DA'}, 'Anwesenheit'),
])
def test_ungueltige_angaben(lr, broken, message):
    res = _put(lr['maria'], lr['s1'], [{**_rating(lr['Budi']), **broken}, _rating(lr['Sari']), _absent(lr['Dewi'])])
    assert res.status_code == 400
    assert res.get_json()['error'].startswith('Budi: ') and message in res.get_json()['error']
    assert lr['maria'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings').get_json()['summary']['rated'] == 0


def test_fehlende_bekommen_keine_sterne_und_niemand_wird_vergessen(lr):
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), {**_rating(lr['Dewi']), 'attendance': 'ABSENT'}])
    assert res.status_code == 400 and 'Nur anwesende' in res.get_json()['error']
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari'])])
    assert res.status_code == 400 and 'Dewi' in res.get_json()['error']
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi']), _rating(lr['Eka'])])
    assert res.status_code == 400 and 'Teilnehmer dieses Kurses' in res.get_json()['error']


def test_wer_nachtraeglich_fehlt_verliert_die_sterne(lr):
    _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'])])
    body = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _absent(lr['Sari'], 'EXCUSED'), _absent(lr['Dewi'])]).get_json()
    assert body['summary']['rated'] == 1
    _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'])])
    res = lr['maria'].put(f'/api/sessions/{lr["s1"]}/attendance',                       # alte Anwesenheits-Erfassung
                          json={'entries': [{'trainee_id': lr['Budi'], 'status': 'ABSENT'}]})
    assert res.status_code == 200
    assert lr['maria'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings').get_json()['summary']['rated'] == 1
    log = lr['admin'].get('/api/activity?action=attendance.record').get_json()['activity'][0]
    assert list(log['detail']['lesson_ratings_removed']) == ['Budi']


def test_zukunft_und_abgesagt_gesperrt(lr):
    future = lr['session'](lr['k1'], -2, lr['m2'])
    res = _put(lr['maria'], future, [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'])])
    assert res.status_code == 409


def test_reichweite_und_rechte(lr):
    assert lr['tom'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings').status_code == 404
    assert _put(lr['tom'], lr['s1'], [_rating(lr['Budi'])]).status_code == 404
    assert lr['hr'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings').status_code == 200          # lesen ja
    assert _put(lr['hr'], lr['s1'], [_rating(lr['Budi'])]).status_code == 403                   # erfassen nein
    assert lr['tom'].get(f'/api/courses/{lr["k1"]}/lesson-report').status_code == 404
    assert lr['budi'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings').status_code == 403


def test_live_vorschau(lr):
    res = lr['maria'].post('/api/lesson-ratings/evaluate', json={'homework_none': False, 'entries': [
        _rating(lr['Budi']), {'trainee_id': lr['Sari'], 'v': 3}]})
    assert res.status_code == 200
    assert res.get_json()['results'] == {
        str(lr['Budi']): {'part_a': 12, 'part_b': 4, 'total': 16, 'level': 'B', 'capped': False, 'complete': True},
        str(lr['Sari']): {'part_a': None, 'part_b': None, 'total': None, 'level': None, 'capped': False,
                          'complete': False}}


def test_kandidat_sieht_eigene_rueckmeldung_ohne_notiz(lr):
    _put(lr['maria'], lr['s1'], [_rating(lr['Budi'], note='GEHEIM'), _rating(lr['Sari']), _absent(lr['Dewi'])])
    body = lr['budi'].get('/api/my-lesson-ratings').get_json()
    assert len(body['ratings']) == 1
    mine = body['ratings'][0]
    assert (mine['strength'], mine['target'], mine['result']['level'], mine['unit']) == (['W'], ['P'], 'B', 1)
    assert mine['module']['name'] == 'Modul 1'
    text = str(body)
    assert 'GEHEIM' not in text and 'maria' not in text and "'note'" not in text
    assert [r['trainee_id'] for r in lr['sari'].get('/api/my-lesson-ratings').get_json()['ratings']] == [lr['Sari']]


def test_auswertung_je_gruppe(lr):
    _put(lr['maria'], lr['s1'], [_rating(lr['Budi'], stars=(2, 2, 2, 2, 2), pu=0, mi=1, ha=1),
                                 _rating(lr['Sari'], stars=(1, 2, 2, 1, 1), pu=0, mi=0, ha=0, strength='L', target='V'),
                                 _absent(lr['Dewi'])])
    _put(lr['maria'], lr['s2'], [_rating(lr['Budi'], stars=(3, 3, 3, 3, 3), ha=2),
                                 _rating(lr['Sari'], stars=(1, 1, 2, 1, 1), pu=0, mi=0, ha=0, strength='L', target='V'),
                                 _rating(lr['Dewi'], stars=(3, 3, 3, 3, 2), ha=2)])
    report = lr['maria'].get(f'/api/courses/{lr["k1"]}/lesson-report').get_json()
    assert report['period'] == {'from': None, 'to': None}
    assert report['group']['count'] == 5
    assert report['group']['weakest'] == ['p']
    rows = {p['trainee']['name']: p for p in report['participants']}
    assert rows['Budi']['count'] == 2 and rows['Budi']['average']['total'] == 16.0           # 12 und 20
    assert rows['Budi']['latest']['level'] == 'A' and rows['Budi']['latest']['unit'] == 2
    assert rows['Sari']['latest']['level'] == 'D' and rows['Sari']['levels'] == {'D': 2}
    assert [t['name'] for t in report['coaching']] == ['Sari']
    assert [t['name'] for t in report['challenge']] == ['Budi', 'Dewi']
    assert [(s['unit'], s['rated']) for s in report['sessions']] == [(1, 2), (2, 3)]
    # Trend: Zeitraum = nur der 2. Termin, Vergleich mit dem Tag davor
    day2 = report['sessions'][1]['date']
    trend = lr['maria'].get(f'/api/courses/{lr["k1"]}/lesson-report?from={day2}&to={day2}').get_json()
    budi = next(p for p in trend['participants'] if p['trainee']['name'] == 'Budi')
    assert (budi['average']['total'], budi['previous_total'], budi['trend']) == (20.0, 12.0, 8.0)
    assert lr['maria'].get(f'/api/courses/{lr["k1"]}/lesson-report?from={day2}').status_code == 400


def test_offene_bewertungen_und_handlungsbedarf(lr):
    def open_ids():
        return [s['id'] for s in lr['maria'].get('/api/my-teaching').get_json()['open_lesson_ratings']]
    assert open_ids() == [lr['s3'], lr['s2'], lr['s1']]
    _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari'], stars=(1, 1, 1, 1, 1), pu=0, mi=0, ha=0),
                                 _absent(lr['Dewi'])])
    assert open_ids() == [lr['s3'], lr['s2']]
    lr['maria'].put(f'/api/sessions/{lr["s2"]}/attendance', json={'entries': [   # nur Anwesenheit -> weiter offen
        {'trainee_id': lr['Budi'], 'status': 'PRESENT'}]})
    assert lr['s2'] in open_ids()
    attention = lr['admin'].get('/api/dashboard').get_json()['attention']
    assert [p['name'] for p in attention['lesson_coaching']['items']] == ['Sari']
    assert attention['open_lesson_ratings']['count'] == 2
    profile = lr['maria'].get(f'/api/candidates/{lr["Sari"]}').get_json()
    assert profile['lesson_ratings']['ratings'][0]['result']['level'] == 'D'


def test_mehrere_module_und_einheiten_in_einem_termin(lr):
    """Die Dozentinnen behandeln oft 2–3 Module je Termin, auch zwei Einheiten desselben Moduls am selben Tag."""
    group = lambda stars: [_rating(lr['Budi'], stars=stars), _rating(lr['Sari']), _absent(lr['Dewi'])]  # noqa: E731
    assert _put(lr['maria'], lr['s1'], group((2, 2, 2, 2, 2)), module_id=lr['m1'], unit=1).status_code == 200
    assert _put(lr['maria'], lr['s1'], group((3, 3, 3, 3, 3)), module_id=lr['m2'], unit=1).status_code == 200
    assert _put(lr['maria'], lr['s1'], group((3, 3, 3, 3, 2)), module_id=lr['m2'], unit=2).status_code == 200
    first = lr['maria'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings').get_json()
    assert [(x['module']['id'], x['unit'], x['rated']) for x in first['sheets']] == [
        (lr['m1'], 1, 2), (lr['m2'], 1, 2), (lr['m2'], 2, 2)]
    assert first['sheet'] == {'module': {'id': lr['m1'], 'name': 'Modul 1'}, 'unit': 1}       # erstes Blatt
    assert [m['name'] for m in first['modules']] == ['Modul 1', 'Modul 2']
    other = lr['maria'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings?module_id={lr["m2"]}&unit=2').get_json()
    budi = next(e for e in other['entries'] if e['trainee']['name'] == 'Budi')
    assert budi['rating']['result']['total'] == 18 and budi['rating']['module']['id'] == lr['m2']
    # naechste Einheit wird vorgeschlagen; Bericht zeigt je Blatt eine Zeile
    assert lr['maria'].get(f'/api/sessions/{lr["s2"]}/lesson-ratings?module_id={lr["m2"]}').get_json()['sheet'][
        'unit'] == 3
    report = lr['maria'].get(f'/api/courses/{lr["k1"]}/lesson-report').get_json()
    assert [(x['module']['name'], x['unit']) for x in report['sessions']] == [
        ('Modul 1', 1), ('Modul 2', 1), ('Modul 2', 2)]
    assert next(p for p in report['participants'] if p['trainee']['name'] == 'Budi')['count'] == 3
    overall = lr['admin'].get(f'/api/overall/{lr["Budi"]}').get_json()
    assert overall['parts']['german']['count'] == 3


def test_modul_muss_zum_curriculum_passen(lr):
    admin = lr['admin']
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    pid = admin.post('/api/programs', json={'name': 'Anderes Programm'}).get_json()['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    foreign = admin.post(f'/api/curricula/{cur}/modules', json={'name': 'Fremd'}).get_json()['id']
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'])],
               module_id=foreign, unit=1)
    assert res.status_code == 400 and res.get_json()['field'] == 'module_id'
    assert lr['maria'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings?module_id={foreign}').status_code == 400
    assert lr['maria'].get(f'/api/sessions/{lr["s1"]}/lesson-ratings?unit=0').status_code == 400


def test_leere_felder_werden_ignoriert(lr):
    """Leere Sterne/Pü/Mi/Stärke/Ziel sind gewollt: gespeichert ohne Gesamt; ganz ohne Werte = ohne Bewertung."""
    entries = [_rating(lr['Budi'], stars=(3, 3, None, 3, 3), strength=None, target=None),
               {'trainee_id': lr['Sari'], 'attendance': 'PRESENT'}, _absent(lr['Dewi'])]
    res = _put(lr['maria'], lr['s1'], entries)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    budi, sari = (next(e for e in body['entries'] if e['trainee']['name'] == n) for n in ('Budi', 'Sari'))
    assert (budi['rating']['w'], budi['rating']['strength'], budi['rating']['target']) == (None, [], [])
    assert budi['rating']['result'] == {'part_a': None, 'part_b': None, 'total': None, 'level': None,
                                        'capped': False, 'complete': False}
    assert sari['rating'] is None and sari['attendance']['status'] == 'PRESENT'
    assert body['summary']['rated'] == 1
    log = lr['admin'].get('/api/activity?action=lesson_rating.record').get_json()['activity'][0]
    assert log['detail']['changes']['Budi'][1] == ('Modul 1 E1 · V3 R3 W– F3 P3 · Pü1 Mi2 HA1 · ohne Gesamt · '
                                                   'Stärke – · Ziel –')
    # ohne Gesamt: kein Level, kein Deutsch-Teil, Auswertung zaehlt den Aspekt nur gefuellt
    report = lr['maria'].get(f'/api/courses/{lr["k1"]}/lesson-report').get_json()
    row = next(p for p in report['participants'] if p['trainee']['name'] == 'Budi')
    assert (row['count'], row['average']['total'], row['average']['aspects']['w'], row['latest']) == (1, None, None, None)
    assert row['average']['aspects']['v'] == 3
    assert lr['admin'].get(f'/api/overall/{lr["Budi"]}').get_json()['parts']['german']['score'] is None


def test_mehrere_codes_fuer_staerke_und_ziel(lr):
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi'], strength=['L', 'V', 'R'], target='F'),
                                       _rating(lr['Sari']), _absent(lr['Dewi'])])
    budi = next(e for e in res.get_json()['entries'] if e['trainee']['name'] == 'Budi')
    assert (budi['rating']['strength'], budi['rating']['target']) == (['V', 'R', 'L'], ['F'])   # feste Reihenfolge
    log = lr['admin'].get('/api/activity?action=lesson_rating.record').get_json()['activity'][0]
    assert log['detail']['changes']['Budi'][1].endswith('Stärke V R L · Ziel F')


def test_wer_fehlt_verliert_die_sterne_aller_module_des_termins(lr):
    for module in (lr['m1'], lr['m2']):
        _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'])],
             module_id=module, unit=1)
    body = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _absent(lr['Sari']), _absent(lr['Dewi'])],
                module_id=lr['m1'], unit=1).get_json()
    assert [(x['module']['id'], x['rated']) for x in body['sheets']] == [(lr['m1'], 1), (lr['m2'], 1)]
    log = lr['admin'].get('/api/activity?action=lesson_rating.record').get_json()['activity'][0]
    assert sorted(log['detail']['changes']) == ['Sari', 'Sari (Modul 2 E1)']


def test_gruppenwechsel_bleibt_korrigierbar(lr):
    """Wer die Gruppe wechselt, bleibt in den alten Terminen korrigierbar (Anwesenheit + Sterne) — freiwillig,
    niemand muss ihn mitsenden. Wer nie in der Gruppe war, bleibt draussen."""
    _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'])])
    assert lr['admin'].delete(f'/api/courses/{lr["k1"]}/participants/{lr["Dewi"]}', json={}).status_code == 200
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari'])])           # ohne Dewi: erlaubt
    assert res.status_code == 200, res.get_json()
    dewi = next(e for e in res.get_json()['entries'] if e['trainee']['name'] == 'Dewi')
    assert (dewi['trainee']['in_course'], dewi['attendance']['status'], dewi['rating']) == (False, 'ABSENT', None)
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _rating(lr['Dewi'], stars=(2, 2, 2, 2, 2))])
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    dewi = next(e for e in body['entries'] if e['trainee']['name'] == 'Dewi')
    assert (dewi['attendance']['status'], dewi['rating']['v']) == ('PRESENT', 2)
    assert body['summary'] == {'expected': 2, 'attended': 3, 'rated': 3}
    log = lr['admin'].get('/api/activity?action=lesson_rating.record').get_json()['activity'][0]
    assert log['detail']['attendance']['Dewi'] == ['Abwesend', 'Anwesend']
    # Sterne einzeln wieder entfernen (alle Felder leer), Anwesenheit bleibt
    body = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']),
                                        {'trainee_id': lr['Dewi'], 'attendance': 'PRESENT'}]).get_json()
    dewi = next(e for e in body['entries'] if e['trainee']['name'] == 'Dewi')
    assert (dewi['attendance']['status'], dewi['rating'], body['summary']['rated']) == ('PRESENT', None, 2)
    # auch an einem alten Termin ohne eigenen Eintrag (frueherer Teilnehmer des Kurses)
    res = _put(lr['maria'], lr['s2'], [_rating(lr['Budi']), _rating(lr['Sari']), _rating(lr['Dewi'])])
    assert res.status_code == 200, res.get_json()
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _rating(lr['Eka'])])
    assert res.status_code == 400 and 'Teilnehmer dieses Kurses' in res.get_json()['error']
    lr['admin'].post(f'/api/candidates/{lr["Dewi"]}/archive', json={})
    res = _put(lr['maria'], lr['s1'], [_rating(lr['Budi']), _rating(lr['Sari']), _absent(lr['Dewi'], 'EXCUSED')])
    assert res.status_code == 400


def _move(client, sid, **body):
    return client.post(f'/api/sessions/{sid}/lesson-ratings/move', json=body)


def test_blatt_umhaengen(lr):
    """Falsches Modul gewaehlt: das ganze Blatt wandert, Sterne/Notizen/Anwesenheit bleiben; nie still zusammenfuehren."""
    group = [_rating(lr['Budi'], note='gut'), _rating(lr['Sari']), _absent(lr['Dewi'])]
    _put(lr['maria'], lr['s1'], group, module_id=lr['m1'], unit=1)
    res = _move(lr['maria'], lr['s1'], module_id=lr['m1'], unit=1, to_module_id=lr['m2'], to_unit=2)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body['sheet'] == {'module': {'id': lr['m2'], 'name': 'Modul 2'}, 'unit': 2}
    assert [(x['module']['id'], x['unit'], x['rated']) for x in body['sheets']] == [(lr['m2'], 2, 2)]
    budi = next(e for e in body['entries'] if e['trainee']['name'] == 'Budi')
    assert (budi['rating']['note'], budi['rating']['result']['total']) == ('gut', 16)
    log = lr['admin'].get('/api/activity?action=lesson_rating.move').get_json()['activity'][0]
    assert log['detail']['count'] == 2 and 'Modul 1 (Einheit 1) -> Modul 2 (Einheit 2)' in log['summary']
    # leeres Blatt, gleiches Ziel, belegtes Ziel, fremdes Modul, fremder Dozent
    assert _move(lr['maria'], lr['s1'], module_id=lr['m1'], unit=1, to_module_id=lr['m2'], to_unit=1).status_code == 409
    assert _move(lr['maria'], lr['s1'], module_id=lr['m2'], unit=2, to_module_id=lr['m2'], to_unit=2).status_code == 400
    _put(lr['maria'], lr['s1'], group, module_id=lr['m1'], unit=1)
    res = _move(lr['maria'], lr['s1'], module_id=lr['m1'], unit=1, to_module_id=lr['m2'], to_unit=2)
    assert res.status_code == 409 and 'schon Bewertungen' in res.get_json()['error']
    assert _move(lr['maria'], lr['s1'], module_id=lr['m1'], unit=1).status_code == 400
    assert _move(lr['maria'], lr['s1'], module_id=lr['m1'], unit=1, to_module_id=999999).status_code == 400
    assert _move(lr['tom'], lr['s1'], module_id=lr['m1'], unit=1, to_module_id=lr['m2']).status_code == 404
    assert _move(lr['hr'], lr['s1'], module_id=lr['m1'], unit=1, to_module_id=lr['m2']).status_code == 403

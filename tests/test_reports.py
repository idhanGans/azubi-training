"""Berichte: Anwesenheit, Leistung, Dozenten, Kandidatenbericht — Zeitraum, Filter, CSV, Rechte."""
from datetime import timedelta

import pytest

from app.services.local_time import today


def _day(days):
    return (today() + timedelta(days=days)).isoformat()


@pytest.fixture
def rep(as_user, grant, trainee):
    admin = as_user('root_admin')
    levels = {e['code']: e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries']}
    admin.post('/api/programs', json={'name': 'Sprechkurs'})
    pid = admin.get('/api/programs').get_json()['programs'][0]['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': levels['B1']}).get_json()['id']
    mods = [admin.post(f'/api/curricula/{cur}/modules', json={'name': f'M{n}'}).get_json()['id'] for n in range(1, 5)]
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [levels['B1']]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    budi = trainee('Budi', msh_user='budi', current_level_id=levels['B1'], abteilung='Berlin')
    sari = trainee('=HYPERLINK("x")', current_level_id=levels['A2'])       # CSV-Injection-Versuch im Namen
    dewi = trainee('Dewi', current_level_id=levels['B1'])
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': levels['B1'], 'instructor_id': ids['maria'],
                                          'module_id': mods[1], 'status': 'RUNNING'}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': levels['B1'],
                                          'instructor_id': ids['tom']}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi, sari]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})

    def session(course, days, start='09:00', end='11:00'):
        return admin.post('/api/sessions', json={'course_id': course, 'date': _day(days), 'start': start,
                                                 'end': end}).get_json()['sessions'][0]['id']
    s_old = session(k1, -120)                                 # ausserhalb der 90 Tage
    s1, s2 = session(k1, -10), session(k1, -3)
    session(k1, 5)                                            # geplant
    for sid, b, s in ((s_old, 'ABSENT', 'ABSENT'), (s1, 'PRESENT', 'ABSENT'), (s2, 'LATE', 'EXCUSED')):
        entries = [{'trainee_id': budi, 'status': b}, {'trainee_id': sari, 'status': s}]
        if b == 'LATE':
            entries[0]['minutes_late'] = 15
        admin.put(f'/api/sessions/{sid}/attendance', json={'entries': entries})
    tpl = admin.post('/api/assessment-templates', json={'name': 'Monat', 'passing_percent': 60, 'categories': [
        {'name': 'Lesen', 'max_score': 10, 'weight': 1}, {'name': 'Sprechen', 'max_score': 10, 'weight': 1}]}).get_json()

    def assess(tid, pts, days, final=True, **extra):
        body = {'trainee_id': tid, 'template_id': tpl['id'], 'instructor_id': ids['maria'], 'course_id': k1,
                'assessed_on': _day(days), 'scores': [{'category_id': c['id'], 'points': p}
                                                      for c, p in zip(tpl['categories'], pts)], **extra}
        aid = admin.post('/api/assessments', json=body).get_json()['assessment']['id']
        if final:
            admin.post(f'/api/assessments/{aid}/finalize')
    assess(budi, (4, 4), -150)                                 # alt, ausserhalb
    assess(budi, (8, 6), -20, recommendations='Weiter so', internal_note='NUR-INTERN')
    assess(budi, (9, 9), -2)
    assess(sari, (5, 5), -5)
    assess(sari, (1, 1), -1, final=False)
    grant('lea', 'ACADEMIC_MANAGER')
    return {'admin': admin, 'lea': as_user('lea'), 'budi': budi, 'sari': sari, 'dewi': dewi, 'k1': k1,
            'levels': levels}


def _table(body, tid):
    return next(t for t in body['tables'] if t['id'] == tid)


def test_anwesenheitsbericht_zeitraum_und_zahlen(rep):
    body = rep['lea'].get('/api/reports/attendance').get_json()
    rows = {r['name']: r for r in _table(body, 'candidates')['rows']}
    assert (rows['Budi']['present'], rows['Budi']['late'], rows['Budi']['absent']) == (1, 1, 0)   # alter Termin fehlt
    assert rows['Budi']['rate'] == 1.0 and rows['Budi']['minutes_late'] == 15
    assert rows['Budi']['courses'] == ['Kurs Maria']
    assert (rows['Dewi']['recorded'], rows['Dewi']['rate']) == (0, None)
    course = _table(body, 'courses')['rows'][0]
    assert (course['course'], course['sessions'], course['present'], course['excused']) == ('Kurs Maria', 2, 1, 1)
    assert body['summary']['absences'] == 1 and body['summary']['late'] == 1
    wide = rep['lea'].get(f'/api/reports/attendance?from={_day(-130)}&to={_day(0)}').get_json()
    assert {r['name']: r['absent'] for r in _table(wide, 'candidates')['rows']}['Budi'] == 1
    only_b1 = rep['lea'].get(f'/api/reports/attendance?level_id={rep["levels"]["B1"]}').get_json()
    assert [r['name'] for r in _table(only_b1, 'candidates')['rows']] == ['Budi', 'Dewi']


def test_leistungsbericht(rep):
    body = rep['lea'].get('/api/reports/academic').get_json()
    tpl = _table(body, 'templates')['rows'][0]
    assert (tpl['assessments'], tpl['candidates'], tpl['avg'], tpl['pass_rate']) == (3, 2, 70.0, 0.6667)
    skills = {r['skill']: r for r in _table(body, 'skills')['rows']}
    assert skills['Lesen']['avg'] == 73.3 and (skills['Sprechen']['min'], skills['Sprechen']['max']) == (50.0, 90.0)
    people = {r['name']: r for r in _table(body, 'candidates')['rows']}
    assert (people['Budi']['assessments'], people['Budi']['latest'], people['Budi']['passed']) == (2, 90.0, True)
    assert people['Dewi']['latest'] is None
    mod = _table(body, 'modules')['rows'][0]
    assert (mod['course'], mod['participants'], mod['completed'], mod['total'], mod['percent']) == ('Kurs Maria', 2, 1, 4,
                                                                                                    25.0)
    assert mod['status'] == 'Laufend'                                 # deutsch, auch in der CSV — kein RUNNING
    assert body['summary']['avg_latest'] == 70.0                     # (90 + 50) / 2


def test_dozentenbericht(rep):
    body = rep['lea'].get(f'/api/reports/instructors?to={_day(10)}').get_json()   # inkl. geplanter Termin in 5 Tagen
    rows = {r['instructor']: r for r in _table(body, 'instructors')['rows']}
    maria = rows['Maria']
    assert (maria['sessions_held'], maria['hours_held'], maria['hours_planned']) == (2, 4.0, 2.0)
    assert (maria['courses'], maria['running'], maria['candidates']) == (1, 1, 2)
    assert (maria['assessments_final'], maria['assessments_open']) == (3, 1)
    assert (rows['Tom']['hours_held'], rows['Tom']['candidates']) == (0, 1)


def test_kandidatenbericht_ohne_interne_notiz(rep):
    res = rep['lea'].get(f'/api/reports/candidates/{rep["budi"]}')
    body = res.get_json()
    assert 'NUR-INTERN' not in res.get_data(as_text=True)
    assert [a['overall_percent'] for a in body['assessments']] == [40.0, 70.0, 90.0]      # seit Beginn
    assert body['feedback'] == [{'date': _day(-20), 'template': 'Monat', 'recommendations': 'Weiter so'}]
    assert body['period']['from'] == _day(-150)                      # ganzer Verlauf ab erster Bewertung
    assert body['attendance']['total']['absent'] == 1 and body['attendance']['period'] == body['attendance']['total']
    assert {s['skill'] for s in body['progress']['skills']} == {'READING', 'SPEAKING'}
    short = rep['lea'].get(f'/api/reports/candidates/{rep["budi"]}?from={_day(-5)}').get_json()
    assert [a['overall_percent'] for a in short['assessments']] == [90.0]
    assert short['attendance']['period']['absent'] == 0 and short['attendance']['total']['absent'] == 1
    assert rep['lea'].get('/api/reports/candidates/99999').status_code == 404


def test_csv_export_excel_tauglich_und_protokolliert(rep):
    res = rep['lea'].get('/api/reports/attendance?format=csv&table=candidates')
    assert res.status_code == 200 and res.mimetype == 'text/csv'
    assert 'attachment; filename="attendance_candidates_' in res.headers['Content-Disposition']
    text = res.get_data(as_text=True)
    assert text.startswith('﻿Nr.;Name;Abteilung;Kurse;Anwesend')
    assert 'Quote (%)' in text.splitlines()[0]
    budi = next(line for line in text.splitlines() if ';Budi;' in line)
    assert budi.split(';')[-2:] == ['100', '15']                               # Quote in %, Minuten
    assert "'=HYPERLINK" in text and '\n=HYPERLINK' not in text and ';=HYPERLINK' not in text
    academic = rep['lea'].get('/api/reports/academic?format=csv&table=candidates').get_data(as_text=True)
    assert _day(-2)[8:10] + '.' + _day(-2)[5:7] + '.' in academic and ';Ja' in academic
    log = rep['admin'].get('/api/activity').get_json()['activity'][0]
    assert log['action'] == 'report.export' and 'Leistungsbericht' in log['summary']


@pytest.mark.parametrize('query,field', [
    ('from=2026-13-01', 'from'), ('from=2026-09-10&to=2026-09-01', 'from'), ('from=2023-01-01&to=2026-01-01', 'from'),
    ('format=csv&table=gibtsnicht', 'table'), ('course_id=abc', 'course_id'),
])
def test_ungueltige_filter(rep, query, field):
    res = rep['lea'].get(f'/api/reports/attendance?{query}')
    assert res.status_code == 400 and res.get_json()['field'] == field


@pytest.mark.parametrize('role,status', [('HR', 200), ('MANAGEMENT', 200), ('ACADEMIC_MANAGER', 200),
                                         ('INSTRUCTOR', 403)])
def test_rechte(rep, as_user, grant, role, status):
    grant('person', role)
    for path in ('/api/reports/attendance', '/api/reports/academic', '/api/reports/instructors',
                 f'/api/reports/candidates/{rep["budi"]}'):
        assert as_user('person').get(path).status_code == status, path
    assert as_user('budi').get('/api/reports/attendance').status_code == 403

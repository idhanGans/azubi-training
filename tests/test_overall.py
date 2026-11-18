"""Overall rating (topic meeting "Azubi 2027"): report 10% + German 40% + SPV 30% + internal 20%.

Calculation example (period Mon 28.09. – Fri 02.10.2026, 5 workdays) — checked by hand:
- Report: 6 h + 6 h + 10 h (counts as 8) + 4 h = 24 of 30 h = 80%; 4 of 5 workdays = 80%; thoroughness
  (1 + 0.25 + 1 + 1) / 4 = 81.25%  ->  50·0.8 + 25·0.8 + 25·0.8125 = 80.3
- German: module ratings 20 and 13 points -> avg 16.5 of 20 = 82.5%; attendance 2 of 3 = 66.67%
  ->  75·0.825 + 25·0.6667 = 78.5
- SPV: SPV avg 8 and leader avg 6 -> 7 of 10 = 70.0;  Internal: avg 9 -> 90.0
- Total: 8.03 + 31.4 + 21 + 18 = 78.43 -> 78.4
"""
import io
from datetime import date

import pytest
from openpyxl import load_workbook
from sqlalchemy import text

from app.models.training_report import TrainingReport
from app.services import overall

PERIOD = '?from=2026-09-28&to=2026-10-02'
STARS3 = {a: 3 for a in 'vrwfp'}
STARS2 = {a: 2 for a in 'vrwfp'}


def _rate(as_user, login, tid, scores, db, day='2026-09-30', month=1):
    rid = as_user(login).post('/api/ratings', json={
        'trainee_id': tid, 'month': month, 'r_practical': scores[0], 'r_reliability': scores[1],
        'r_motivation': scores[2], 'note': f'Notiz von {login}'}).get_json()['id']
    db.session.execute(text("UPDATE staff_rating SET created_at = CAST(:d AS date) + interval '3 hours' WHERE id = :i"),
                       {'d': day, 'i': rid})
    db.session.commit()


@pytest.fixture
def world(as_user, trainee, db):
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    pid = admin.post('/api/programs', json={'name': 'Deutsch'}).get_json()['id']
    cur = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': b1}).get_json()['id']
    module = admin.post(f'/api/curricula/{cur}/modules', json={'name': 'Modul 1'}).get_json()['id']
    bad = admin.post('/api/departments', json={'name': 'Bad Neuenahr', 'leaders': ['kurt']}).get_json()['id']
    erk = admin.post('/api/departments', json={'name': 'Erkelenz'}).get_json()['id']
    dimo = trainee('Dimas', department_id=bad, supervisor='hanan', abteilung='Bad Neuenahr – Elektro')
    fajar = trainee('Fajar', department_id=bad, supervisor='endah')
    raka = trainee('Raka', department_id=erk, supervisor='citra')
    course = admin.post('/api/courses', json={'name': 'Gruppe 2', 'level_id': b1, 'module_id': module,
                                              'status': 'RUNNING'}).get_json()['id']
    admin.post(f'/api/courses/{course}/participants', json={'trainee_ids': [dimo]})

    def lesson(day, entry):
        sid = admin.post('/api/sessions', json={'course_id': course, 'date': day, 'start': '15:00', 'end': '17:00',
                                                'module_id': module}).get_json()['sessions'][0]['id']
        assert admin.put(f'/api/sessions/{sid}/lesson-ratings', json={'homework_none': 'ha' not in entry, 'entries': [
            {'trainee_id': dimo, **entry}]}).status_code == 200
    lesson('2026-09-28', {'attendance': 'PRESENT', **STARS3, 'pu': 1, 'mi': 2, 'strength': 'V', 'target': 'R'})
    lesson('2026-09-30', {'attendance': 'PRESENT', **STARS2, 'pu': 1, 'mi': 1, 'ha': 1, 'strength': 'W',
                          'target': 'F'})
    lesson('2026-10-02', {'attendance': 'ABSENT'})
    for day, hours, chars in (('2026-09-28', 6, 400), ('2026-09-29', 6, 100), ('2026-09-30', 10, 400),
                              ('2026-10-02', 4, 500), ('2026-10-03', 5, 400)):          # Sat: outside
        db.session.add(TrainingReport(trainee_id=dimo, period=day, hours=hours, learned='x' * chars))
    db.session.commit()
    _rate(as_user, 'hanan', dimo, (8, 7, 9), db)
    _rate(as_user, 'kurt', dimo, (6, 6, 6), db)
    _rate(as_user, 'kurt', fajar, (5, 5, 5), db)
    _rate(as_user, 'root_admin', dimo, (9, 9, 9), db)
    _rate(as_user, 'root_admin', dimo, (1, 1, 1), db, day='2026-10-05', month=2)         # after the period
    return {'admin': admin, 'hanan': as_user('hanan'), 'kurt': as_user('kurt'), 'citra': as_user('citra'), 'dimo': dimo,
            'fajar': fajar, 'raka': raka, 'bad': bad, 'erk': erk}


def test_werktage():
    assert overall.workdays(date(2026, 9, 28), date(2026, 10, 2)) == 5
    assert overall.workdays(date(2026, 9, 26), date(2026, 10, 11)) == 10        # Sat .. Sun: two full weeks
    assert overall.workdays(date(2026, 10, 3), date(2026, 10, 4)) == 0
    assert overall.workdays(date(2026, 10, 5), date(2026, 10, 1)) == 0


def test_rechenbeispiel(world):
    body = world['admin'].get(f'/api/overall/{world["dimo"]}{PERIOD}').get_json()
    report, german, spv, intern = (body['parts'][k] for k in ('report', 'german', 'spv', 'intern'))
    assert (report['workdays'], report['days_reported'], report['hours'], report['target_hours']) == (5, 4, 24.0, 30)
    assert (report['hours_percent'], report['regularity_percent'], report['detail_percent'], report['score']) == (
        80.0, 80.0, 81.2, 80.3)
    assert (german['count'], german['average_total'], german['lessons_percent'], german['score']) == (2, 16.5, 82.5, 78.5)
    assert german['attendance'] == {'present': 2, 'late': 0, 'excused': 0, 'absent': 1, 'rate': 0.6667}
    assert german['latest_level'] == 'C'
    assert (spv['count'], spv['mean'], spv['score']) == (2, 7.0, 70.0)
    assert (intern['count'], intern['score']) == (1, 90.0)                     # the one from 05.10. doesn't count
    assert (body['total'], body['missing'], body['rank'], body['department_rank']) == (78.4, [], 1, 1)
    assert body['rules']['weights'] == {'report': 10, 'german': 40, 'spv': 30, 'intern': 20}
    assert body['rules']['parts'] == ['report', 'german', 'spv', 'intern']


def test_fehlender_teil_ist_ausstehend_nie_null(world):
    rows = {r['name']: r for r in world['admin'].get(f'/api/overall{PERIOD}').get_json()['rows']}
    fajar = rows['Fajar']
    assert fajar['parts']['report']['score'] == 0.0                # workdays, but no report = 0 points
    assert fajar['parts']['german']['score'] is None and fajar['parts']['intern']['score'] is None
    # Total + rank already from the parts present: report 0.0 (10%) + SPV 50.0 (30%) = (0 + 1500)/40 = 37.5
    assert (fajar['total'], fajar['missing'], fajar['rank']) == (37.5, ['german', 'intern'], 2)
    assert [r['name'] for r in world['admin'].get(f'/api/overall{PERIOD}').get_json()['rows']] == [
        'Dimas', 'Fajar', 'Raka']                              # descending by total (78.4 / 37.5 / 0.0)


def test_rang_gleiche_punkte_gleicher_platz():
    rows = [{'total': 80.0}, {'total': 90.0}, {'total': 80.0}, {'total': None}, {'total': 70.0}]
    overall._rank(rows, 'rank')
    assert [r.get('rank') for r in rows] == [2, 1, 2, None, 4]


def test_spv_und_leiter_sehen_nur_zugeordnete(world):
    hanan, kurt, citra = world['hanan'], world['kurt'], world['citra']
    body = hanan.get(f'/api/overall{PERIOD}').get_json()
    assert [r['name'] for r in body['rows']] == ['Dimas']
    assert (body['overall_rank'], body['rows'][0]['rank'], body['rows'][0]['department_rank']) == (False, None, 1)
    assert [r['name'] for r in kurt.get('/api/overall').get_json()['rows']] == ['Dimas', 'Fajar']
    assert kurt.get(f'/api/overall?department_id={world["erk"]}').get_json()['rows'] == []
    assert hanan.get(f'/api/overall/{world["fajar"]}').status_code == 404
    assert citra.get(f'/api/overall/{world["dimo"]}').status_code == 404
    detail = hanan.get(f'/api/overall/{world["dimo"]}{PERIOD}').get_json()
    assert detail['all_ratings'] is False and detail['rank'] is None
    assert [(r['rater'], r['note']) for r in detail['ratings']] == [('hanan', 'Notiz von hanan')]  # only own
    team = world['admin'].get(f'/api/overall/{world["dimo"]}{PERIOD}').get_json()
    assert {r['rater'] for r in team['ratings']} == {'hanan', 'kurt', 'root_admin'}


def test_filter_abteilung_und_zeitraum(world):
    admin = world['admin']
    assert [r['name'] for r in admin.get(f'/api/overall?department_id={world["erk"]}').get_json()['rows']] == ['Raka']
    assert admin.get('/api/overall?department_id=999999').status_code == 400
    assert admin.get('/api/overall?from=2026-09-28').status_code == 400              # only both or none
    assert admin.get('/api/overall?from=2026-10-02&to=2026-09-28').status_code == 400
    assert admin.get('/api/overall?format=docx').status_code == 400
    whole = admin.get(f'/api/overall/{world["dimo"]}').get_json()
    assert whole['period'] == {'from': None, 'to': None}
    assert whole['parts']['intern']['count'] == 2                                    # without a period: all


def test_rangliste_zeigt_bewerter_notizen(world):
    admin, dimo = world['admin'], world['dimo']
    rows = {r['id']: r for r in admin.get(f'/api/overall{PERIOD}').get_json()['rows']}
    spv = rows[dimo]['parts']['spv']['notes']
    assert {n['note'] for n in spv} == {'Notiz von hanan', 'Notiz von kurt'}      # SPV + leader
    assert {n['rater'] for n in spv} == {'hanan', 'kurt'}                         # team sees rater
    assert any(n['note'] == 'Notiz von root_admin' for n in rows[dimo]['parts']['intern']['notes'])
    # SPV/leader without assessment.view: only own note, without rater name
    hn = {r['id']: r for r in world['hanan'].get(f'/api/overall{PERIOD}').get_json()['rows']}
    own = hn[dimo]['parts']['spv']['notes']
    assert [n['note'] for n in own] == ['Notiz von hanan'] and own[0]['rater'] is None


def test_review_notizen(world):
    admin, hanan, dimo = world['admin'], world['hanan'], world['dimo']
    body = admin.get('/api/overall').get_json()
    assert body['can_edit_notes'] is True
    assert body['note_checkpoints'][0] == '2026-10-19' and body['note_checkpoints'][-1] == '2026-12-28'
    assert len(body['note_checkpoints']) == 6                       # 2-week cadence 19.10. .. 28.12.
    # Super admin sets a note, it appears in the ranking
    res = admin.put('/api/overall/notes', json={'trainee_id': dimo, 'checkpoint': '2026-10-19', 'text': 'Sehr engagiert.'})
    assert res.status_code == 200 and res.get_json()['text'] == 'Sehr engagiert.'
    rows = {r['id']: r for r in admin.get('/api/overall').get_json()['rows']}
    assert rows[dimo]['notes']['2026-10-19'] == 'Sehr engagiert.'
    # empty text deletes the note again
    assert admin.put('/api/overall/notes', json={'trainee_id': dimo, 'checkpoint': '2026-10-19', 'text': '  '}).status_code == 200
    rows = {r['id']: r for r in admin.get('/api/overall').get_json()['rows']}
    assert '2026-10-19' not in rows[dimo]['notes']
    # unknown checkpoint date (not a 2-week cadence) -> 400
    assert admin.put('/api/overall/notes', json={'trainee_id': dimo, 'checkpoint': '2026-10-20', 'text': 'x'}).status_code == 400
    # not super admin: may read but not write
    assert hanan.get('/api/overall').get_json()['can_edit_notes'] is False
    assert hanan.put('/api/overall/notes', json={'trainee_id': dimo, 'checkpoint': '2026-10-19', 'text': 'x'}).status_code == 403


def test_downloads_excel_und_pdf_nach_rechten(world):
    admin, hanan = world['admin'], world['hanan']
    res = admin.get(f'/api/overall{PERIOD}&format=xlsx')
    assert res.status_code == 200 and res.mimetype.endswith('spreadsheetml.sheet')
    assert 'attachment' in res.headers['Content-Disposition']
    cells = [c for row in load_workbook(io.BytesIO(res.data)).active.iter_rows(values_only=True) for c in row]
    assert {'Dimas', 'Fajar', 'Raka', 'Ausstehend', 78.4} <= set(cells)
    res = hanan.get(f'/api/overall{PERIOD}&format=xlsx')
    cells = [c for row in load_workbook(io.BytesIO(res.data)).active.iter_rows(values_only=True) for c in row]
    assert 'Dimas' in cells and 'Fajar' not in cells and 'Platz' not in cells       # only assigned ones
    pdf = admin.get(f'/api/overall/{world["dimo"]}{PERIOD}&format=pdf')
    assert pdf.status_code == 200 and pdf.mimetype == 'application/pdf' and pdf.data.startswith(b'%PDF')
    single = hanan.get(f'/api/overall/{world["dimo"]}{PERIOD}&format=xlsx')
    cells = [c for row in load_workbook(io.BytesIO(single.data)).active.iter_rows(values_only=True) for c in row]
    assert 'Notiz von hanan' in cells and 'Notiz von kurt' not in cells
    assert hanan.get(f'/api/overall/{world["fajar"]}?format=pdf').status_code == 404
    log = admin.get('/api/activity?action=report.export').get_json()['activity']
    assert [e['actor'] for e in log] == ['hanan', 'root_admin', 'hanan', 'root_admin']
    assert log[0]['summary'].startswith('Azubi-Bericht heruntergeladen: Dimas (XLSX')


def test_excel_fuehrt_keine_formeln_aus(world, as_user):
    admin = as_user('root_admin')
    admin.patch(f'/api/candidates/{world["raka"]}', json={'name': '=HYPERLINK("http://x","y")'})
    res = admin.get('/api/overall?format=xlsx')
    sheet = load_workbook(io.BytesIO(res.data)).active
    cell = next(c for row in sheet.iter_rows() for c in row if str(c.value).startswith('=HYPERLINK'))
    assert cell.data_type == 's'


def test_report_ohne_zeitraum_bis_gestern(world, db, monkeypatch):
    """Without "from" starting at the very first report ever, without "to" until yesterday; a later start date counts."""
    monkeypatch.setattr(overall.local_time, 'today', lambda: date(2026, 10, 3))
    admin = world['admin']
    report = admin.get(f'/api/overall/{world["dimo"]}').get_json()['parts']['report']
    assert (report['from'], report['to'], report['workdays']) == ('2026-09-28', '2026-10-02', 5)
    admin.patch(f'/api/candidates/{world["fajar"]}', json={'start_date': '2026-10-01'})
    fajar = admin.get(f'/api/overall/{world["fajar"]}').get_json()['parts']['report']
    assert (fajar['from'], fajar['workdays']) == ('2026-10-01', 2)
    monkeypatch.setattr(overall.local_time, 'today', lambda: date(2026, 9, 28))
    assert admin.get(f'/api/overall/{world["dimo"]}').get_json()['parts']['report']['score'] is None


def test_abteilungen_pflegen(world, as_user, trainee):
    admin, kurt = world['admin'], world['kurt']
    res = admin.post('/api/departments', json={'name': 'bad neuenahr'})
    assert res.status_code == 409 and res.get_json()['field'] == 'name'
    trainee('Kandidat', msh_user='kandidat')
    assert admin.post('/api/departments', json={'name': 'Verkauf', 'leaders': ['kandidat']}).status_code == 409
    assert admin.post('/api/departments', json={'name': 'Verkauf', 'leaders': 'eko'}).status_code == 400
    assert kurt.post('/api/departments', json={'name': 'X'}).status_code == 403
    res = admin.patch(f'/api/departments/{world["erk"]}', json={'leaders': ['Galih_Santoso', 'markus',
                                                                            'markus']})
    assert res.get_json()['leaders'] == ['galih_santoso', 'markus']
    assert [r['name'] for r in as_user('markus').get('/api/overall').get_json()['rows']] == ['Raka']
    entry = admin.get('/api/activity?action=department.update').get_json()['activity'][0]
    assert entry['detail']['changes']['leaders'] == [[], ['galih_santoso', 'markus']]
    listed = kurt.get('/api/departments').get_json()['departments']
    assert [(d['name'], d['trainee_count'], 'leaders' in d) for d in listed] == [
        ('Bad Neuenahr', 2, False), ('Erkelenz', 1, False)]
    admin.patch(f'/api/departments/{world["erk"]}', json={'active': False})
    res = admin.patch(f'/api/candidates/{world["dimo"]}', json={'department_id': world['erk']})
    assert res.status_code == 400                                     # deactivated: not newly selectable
    assert admin.patch(f'/api/candidates/{world["raka"]}', json={'department_id': world['erk']}).status_code == 200


def test_ohne_daten(as_user):
    body = as_user('root_admin').get('/api/overall').get_json()
    assert (body['rows'], body['departments']) == ([], [])

"""Bewertung durch SPV, Leiter und internes Team (Topik Meeting „Azubi 2027").

- Jeder Login ohne Team-Rolle ist Mitarbeiter (`EVALUATOR`) und erreicht NUR Bewerten + Gesamtbewertung.
- SPV sieht und bewertet nur seine Azubis (`trainee.supervisor`), Leiter alle aktiven seiner Abteilung, das
  interne Team (`rating.internal`) alle aktiven. Von anderen nur Anzahl + Durchschnitt, eigene vollstaendig,
  am Tag der Abgabe korrigierbar.
"""
import json
import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from app import auth

#: Was ein Mitarbeiter ohne Team-Rolle erreicht — ausser den Routen „fuer jeden Angemeldeten".
EVALUATOR_ENDPOINTS = {'pages.ratings', 'pages.overall', 'pages.overall_trainee', 'reports.board',
                       'reports.board_detail', 'reports.add_rating', 'reports.update_rating', 'overall.ranking',
                       'overall.trainee_report', 'overall.trainee_months', 'departments.list_departments'}
SECRET = 'GEHEIM-NOTIZ'
SCORES = {'r_practical': 8, 'r_reliability': 7, 'r_motivation': 9}


@pytest.fixture
def world(as_user, trainee, db):
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    bad = admin.post('/api/departments', json={'name': 'Bad Neuenahr', 'leaders': ['kurt']}).get_json()['id']
    erk = admin.post('/api/departments', json={'name': 'Erkelenz', 'leaders': ['galih_santoso']}).get_json()['id']
    dimo = trainee('Dimas Rio', msh_user='dimas', nickname='Dimo', department_id=bad, supervisor='hanan',
                   abteilung='Bad Neuenahr – Elektro-Assistent', email='dimo@example.org', phone='+62 812 0000 0000')
    fajar = trainee('Fajar Pradipta', department_id=bad, supervisor='endah')
    raka = trainee('Raka Bayu', department_id=erk, supervisor='citra')
    gone = trainee('Archiviert', department_id=bad, supervisor='hanan')
    admin.post(f'/api/candidates/{gone}/archive')
    running = admin.post('/api/courses', json={'name': 'Deutschkurs Gruppe 2', 'level_id': b1,
                                               'status': 'RUNNING'}).get_json()['id']
    done = admin.post('/api/courses', json={'name': 'Alter Kurs', 'level_id': b1}).get_json()['id']
    admin.post(f'/api/courses/{running}/participants', json={'trainee_ids': [dimo]})
    admin.post(f'/api/courses/{done}/participants', json={'trainee_ids': [dimo]})
    admin.patch(f'/api/courses/{done}', json={'status': 'COMPLETED'})
    return {'admin': admin, 'hanan': as_user('hanan'), 'kurt': as_user('kurt'), 'tom': as_user('tom_kollege'),
            'galih': as_user('galih_santoso'), 'dimo': dimo, 'fajar': fajar, 'raka': raka, 'gone': gone}


def _url(rule):
    return re.sub(r'<(?:\w+:)?(\w+)>', '1', rule.rule)


def test_mitarbeiter_erreicht_nur_bewerten_und_gesamtbewertung(app, world):
    """Jede Route, jede Methode: ausser Bewerten, Gesamtbewertung, Abteilungsliste und „wer bin ich" -> 403."""
    hanan = world['hanan']
    open_for_evaluator = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static' or rule.endpoint.startswith('msh_health.'):
            continue
        kind, value = getattr(app.view_functions[rule.endpoint], auth.ACCESS_ATTR)
        if kind == 'authenticated':
            continue
        if kind == 'permission' and value in ('rating.view', 'rating.create'):
            open_for_evaluator.add(rule.endpoint)
            continue
        for method in rule.methods - {'HEAD', 'OPTIONS'}:
            res = hanan._call(method, _url(rule), json={} if method != 'GET' else None)
            assert res.status_code == 403, f'{method} {rule.rule} -> {res.status_code}'
    assert open_for_evaluator == EVALUATOR_ENDPOINTS


def test_seitenleiste_und_startseite(world):
    hanan = world['hanan']
    assert hanan.get('/', headers={'Accept': 'text/html'}).headers['Location'].endswith('/ratings')
    html = hanan.get('/ratings', headers={'Accept': 'text/html'}).get_data(as_text=True)
    links = set(re.findall(r'<a [^>]*href="(/[a-z-]*)"', html.split('id="sidebar"')[1].split('</nav>')[0]))
    assert links == {'/ratings', '/overall'}


def test_wer_wen_sieht(world):
    """SPV: seine; Leiter: ganze Abteilung; ohne Zuordnung: niemand; internes Team: alle aktiven."""
    def board(client):
        return [(x['name'], x['kind'], x['part']) for x in client.get('/api/rating-board').get_json()['trainees']]
    assert board(world['hanan']) == [('Dimas Rio', 'SPV', 'spv')]
    assert board(world['kurt']) == [('Dimas Rio', 'LEITER', 'spv'), ('Fajar Pradipta', 'LEITER', 'spv')]
    assert board(world['galih']) == [('Raka Bayu', 'LEITER', 'spv')]
    assert board(world['tom']) == []
    assert board(world['admin']) == [('Dimas Rio', 'INTERN', 'intern'), ('Fajar Pradipta', 'INTERN', 'intern'),
                                     ('Raka Bayu', 'INTERN', 'intern')]          # archivierte nie
    assert world['hanan'].get('/api/rating-board').get_json()['internal'] is False


def test_bewerten_nur_mit_zuordnung(world):
    hanan, kurt, admin = world['hanan'], world['kurt'], world['admin']
    res = hanan.post('/api/ratings', json={'trainee_id': world['dimo'], **SCORES, 'note': 'Fragt gut nach'})
    assert res.status_code == 201 and res.get_json()['kind'] == 'SPV'
    assert kurt.post('/api/ratings', json={'trainee_id': world['fajar'], **SCORES}).get_json()['kind'] == 'LEITER'
    assert admin.post('/api/ratings', json={'trainee_id': world['raka'], **SCORES}).get_json()['kind'] == 'INTERN'
    for client, tid in ((hanan, world['fajar']), (world['galih'], world['dimo']), (world['tom'], world['dimo']),
                        (hanan, world['gone'])):
        res = client.post('/api/ratings', json={'trainee_id': tid, **SCORES})
        assert res.status_code == 400 and res.get_json()['field'] == 'trainee_id'
        assert client.get(f'/api/rating-board/{tid}').status_code == 404
    assert hanan.post('/api/ratings', json={'trainee_id': world['dimo'], 'r_practical': 8}).get_json()['field'] == \
        'r_reliability'                                                           # alle drei sind Pflicht
    assert hanan.post('/api/ratings', json={'trainee_id': world['dimo'], **SCORES,
                                            'r_motivation': 11}).status_code == 400
    entry = admin.get('/api/activity?action=rating.create').get_json()['activity'][-1]
    assert entry['summary'].startswith('SPV-Bewertung für Dimas Rio, Monat ') and 'Praktische Leistung 8' in entry['summary']


def test_uebersicht_zeigt_durchschnitte_aber_keine_fremden_einzelbewertungen(world):
    hanan, kurt, dimo = world['hanan'], world['kurt'], world['dimo']
    assert hanan.post('/api/ratings', json={'trainee_id': dimo, **SCORES, 'note': SECRET}).status_code == 201
    assert kurt.post('/api/ratings', json={'trainee_id': dimo, 'r_practical': 6, 'r_reliability': 9,
                                            'r_motivation': 7, 'note': 'Leiter-Notiz'}).status_code == 201
    world['admin'].post('/api/ratings', json={'trainee_id': dimo, **SCORES, 'note': 'intern'})
    board = kurt.get('/api/rating-board').get_json()
    assert board['scale'] == [1, 10] and board['categories'] == list(SCORES)
    row = board['trainees'][0]
    assert (row['department'], row['abteilung'], row['groups'], row['nickname']) == (
        {'id': row['department']['id'], 'name': 'Bad Neuenahr'}, 'Bad Neuenahr – Elektro-Assistent',
        ['Deutschkurs Gruppe 2'], 'Dimo')
    stats = row['stats']                                    # nur SPV + Leiter — die interne zaehlt hier nicht
    assert (stats['count'], stats['r_practical'], stats['r_reliability'], stats['r_motivation'], stats['mean'],
            row['rating_mine']) == (2, 7.0, 8.0, 8.0, 7.67, 1)
    detail = kurt.get(f'/api/rating-board/{dimo}').get_json()
    assert [(r['r_practical'], r['note'], r['editable']) for r in detail['mine']] == [(6, 'Leiter-Notiz', True)]
    text_ = json.dumps(board) + json.dumps(detail)
    for hidden in (SECRET, 'hanan', 'dimo@example.org', '+62 812', 'dimas', 'Alter Kurs', 'intern"'):
        assert hidden not in text_, hidden
    assert len(world['admin'].get(f'/api/ratings?trainee_id={dimo}').get_json()['ratings']) == 3  # Team: alle


def test_eigene_bewertung_nur_am_selben_tag_korrigierbar(world, db):
    hanan, kurt = world['hanan'], world['kurt']
    rid = hanan.post('/api/ratings', json={'trainee_id': world['dimo'], **SCORES}).get_json()['id']
    assert kurt.patch(f'/api/ratings/{rid}', json=SCORES).status_code == 404               # fremde
    res = hanan.patch(f'/api/ratings/{rid}', json={**SCORES, 'r_practical': 9, 'note': 'Nachtrag'})
    assert res.status_code == 200
    body = res.get_json()
    assert (body['r_practical'], body['kind'], body['note']) == (9, 'SPV', 'Nachtrag') and body['updated_at']
    entry = world['admin'].get('/api/activity?action=rating.update').get_json()['activity'][0]
    assert entry['actor'] == 'hanan'
    assert entry['detail']['changes']['r_practical'] == [8, 9]
    db.session.execute(text('UPDATE staff_rating SET created_at = created_at - :d WHERE id = :i'),
                       {'d': timedelta(days=1), 'i': rid})
    db.session.commit()
    res = hanan.patch(f'/api/ratings/{rid}', json=SCORES)
    assert res.status_code == 403 and 'Tag der Abgabe' in res.get_json()['error']
    assert hanan.get(f'/api/rating-board/{world["dimo"]}').get_json()['mine'][0]['editable'] is False


def test_zuordnung_wirkt_sofort(world):
    """SPV wechselt: der alte sieht den Azubi nicht mehr, der neue schon; seine alten Bewertungen bleiben."""
    hanan, admin = world['hanan'], world['admin']
    hanan.post('/api/ratings', json={'trainee_id': world['dimo'], **SCORES})
    assert admin.patch(f'/api/candidates/{world["dimo"]}', json={'supervisor': 'Lina'}).status_code == 200
    assert hanan.get('/api/rating-board').get_json()['trainees'] == []
    assert [x['name'] for x in admin.get('/api/rating-board').get_json()['trainees']][0] == 'Dimas Rio'
    profile = world['admin'].get(f'/api/candidates/{world["dimo"]}').get_json()
    assert profile['candidate']['supervisor'] == 'lina'                                        # Login immer klein
    assert len(admin.get(f'/api/ratings?trainee_id={world["dimo"]}').get_json()['ratings']) == 1


def test_spv_muss_mitarbeiter_sein(world, trainee):
    admin = world['admin']
    res = admin.patch(f'/api/candidates/{world["fajar"]}', json={'supervisor': 'dimas'})
    assert res.status_code == 409 and res.get_json()['field'] == 'supervisor'
    res = admin.post('/api/candidates', json={'name': 'Neu', 'msh_user': 'neu', 'supervisor': 'neu'})
    assert res.status_code == 409
    assert admin.patch(f'/api/candidates/{world["fajar"]}', json={'supervisor': 'kein login!'}).status_code == 400


def test_programm_monate():
    from datetime import date
    from app.services.rating_board import PROGRAM_MONTHS, current_month
    assert PROGRAM_MONTHS == 3
    assert [current_month(date.fromisoformat(d)) for d in ('2026-09-01', '2026-09-17', '2026-10-16', '2026-10-17',
                                                            '2026-11-16', '2026-11-17', '2027-03-01')] == [1, 1, 1, 2, 2,
                                                                                                          3, 3]
    from app.services.rating_board import months_info
    calendar = [(c['month'], c['from'], c['to']) for c in months_info()['calendar']]
    assert calendar == [(1, '2026-09-17', '2026-10-16'), (2, '2026-10-17', '2026-11-16'), (3, '2026-11-17', '2026-12-16')]


def test_eine_bewertung_je_monat(world, monkeypatch):
    """Program month 2 is running: one rating per rater and month, month 1 can be made up, month 3 not yet; the
    parts SPV/Intern average the months first (every month counts equally)."""
    monkeypatch.setattr('app.services.rating_board.current_month', lambda today=None: 2)
    hanan, admin, dimo = world['hanan'], world['admin'], world['dimo']
    board = hanan.get('/api/rating-board').get_json()
    assert (board['month'], board['months'], board['program_months']) == (2, [1, 2], 3)
    res = hanan.post('/api/ratings', json={'trainee_id': dimo, **SCORES})                    # default = current month
    assert res.status_code == 201 and res.get_json()['month'] == 2
    res = hanan.post('/api/ratings', json={'trainee_id': dimo, 'month': 2, **SCORES})
    assert res.status_code == 409 and res.get_json()['field'] == 'month'
    res = hanan.post('/api/ratings', json={'trainee_id': dimo, 'month': 3, **SCORES})
    assert res.status_code == 400 and 'noch nicht begonnen' in res.get_json()['error']
    assert hanan.post('/api/ratings', json={'trainee_id': dimo, 'month': 0, **SCORES}).status_code == 400
    low = {'r_practical': 2, 'r_reliability': 2, 'r_motivation': 2}
    assert hanan.post('/api/ratings', json={'trainee_id': dimo, 'month': 1, **low}).status_code == 201   # made up
    assert world['kurt'].post('/api/ratings', json={'trainee_id': dimo, 'month': 2, **low}).status_code == 201
    row = next(x for x in hanan.get('/api/rating-board').get_json()['trainees'] if x['id'] == dimo)
    assert (row['rating_mine'], row['months_mine']) == (2, [1, 2])
    assert {m: (r['r_practical'], r['editable']) for m, r in row['mine'].items()} == {'1': (2, True), '2': (8, True)}
    assert [c['started'] for c in hanan.get('/api/rating-board').get_json()['calendar']] == [True, True, False]
    s = row['stats']                                   # month 1: 2.0, month 2: (8 + 2) / 2 = 5.0 -> parts avg 3.5
    assert (s['count'], s['months']['1']['mean'], s['months']['2']['mean'], s['r_practical'], s['mean']) == (
        3, 2.0, 5.0, 3.5, 3.5)
    detail = hanan.get(f'/api/rating-board/{dimo}').get_json()
    assert [r['month'] for r in detail['mine']] == [2, 1] and sorted(detail['trainee']['mine']) == ['1', '2']
    overall = admin.get(f'/api/overall/{dimo}').get_json()['parts']['spv']
    assert (overall['score'], overall['months']['1']['score'], overall['months']['2']['score']) == (35.0, 20.0, 50.0)
    entry = admin.get('/api/activity?action=rating.create').get_json()['activity'][0]
    assert entry['detail']['month'] == 2 and ', Monat 2:' in entry['summary']

"""Bewertungs-Engine: Vorlagen, Berechnung (eine Stelle), Entwurf/Abschluss/Korrektur, Reichweite, Rechte."""
from datetime import timedelta

import pytest

from app.services.local_time import today
from tests.conftest import _load_migration

TODAY = today().isoformat()

#: Lesen 20 (Gewicht 1, min. 12) + Sprechen 25 = 5 x 5 (Gewicht 2, min. 15), bestanden ab 60 %.
TEMPLATE = {'name': 'Testvorlage', 'passing_percent': 60, 'categories': [
    {'name': 'Lesen', 'max_score': 20, 'weight': 1, 'passing_score': 12},
    {'name': 'Sprechen', 'max_score': 25, 'weight': 2, 'passing_score': 15,
     'criteria': [{'name': n, 'max_score': 5} for n in ('Aussprache', 'Flüssigkeit', 'Wortschatz', 'Grammatik',
                                                        'Interaktion')]}]}


@pytest.fixture
def ex(as_user, grant, trainee):
    """Kurs Maria (Budi, Sari) und Kurs Tom (Dewi); Lea = Studienleitung; eine Vorlage."""
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    ids = {}
    for name in ('maria', 'tom'):
        ids[name] = admin.post('/api/instructors', json={'name': name.title(), 'msh_user': name,
                                                         'level_ids': [b1]}).get_json()['id']
        grant(name, 'INSTRUCTOR')
    grant('lea', 'ACADEMIC_MANAGER')
    budi, sari, dewi = trainee('Budi', msh_user='budi'), trainee('Sari', msh_user='sari'), trainee('Dewi')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Maria', 'level_id': b1, 'instructor_id': ids['maria']}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Tom', 'level_id': b1, 'instructor_id': ids['tom']}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi, sari]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})
    tpl = admin.post('/api/assessment-templates', json=TEMPLATE)
    assert tpl.status_code == 201, tpl.get_json()
    tpl = tpl.get_json()
    lesen, sprechen = tpl['categories']
    return {'admin': admin, 'maria': as_user('maria'), 'tom': as_user('tom'), 'lea': as_user('lea'),
            'ids': ids, 'budi': budi, 'sari': sari, 'dewi': dewi, 'k1': k1, 'k2': k2, 'tpl': tpl,
            'lesen': lesen['id'], 'crit': [c['id'] for c in sprechen['criteria']]}


def _scores(ex, lesen, sprechen):
    return [{'category_id': ex['lesen'], 'points': lesen}] + \
        [{'criterion_id': cid, 'points': p} for cid, p in zip(ex['crit'], sprechen)]


def _create(ex, client='maria', trainee='budi', **body):
    res = ex[client].post('/api/assessments', json={'trainee_id': ex[trainee], 'template_id': ex['tpl']['id'],
                                                    'assessed_on': TODAY, **body})
    assert res.status_code == 201, res.get_json()
    return res.get_json()['assessment']['id']


# ---------- Vorlagen ----------

@pytest.mark.parametrize('change,message', [
    ({'categories': []}, 'mindestens eine Kategorie'),
    ({'categories': [{'name': 'Lesen', 'max_score': 20, 'weight': 0}]}, 'Gewicht'),
    ({'categories': [{'name': 'Lesen', 'max_score': 20, 'weight': 1}, {'name': 'lesen', 'max_score': 5, 'weight': 1}]},
     'doppelt'),
    ({'categories': [{'name': 'Lesen', 'max_score': 20, 'weight': 1, 'passing_score': 21}]}, 'Mindestpunkte dürfen'),
    ({'categories': [{'name': 'Lesen', 'max_score': 20.3, 'weight': 1}]}, '0,5'),
    ({'categories': [{'name': 'Sprechen', 'max_score': 20, 'weight': 1,
                      'criteria': [{'name': 'A', 'max_score': 5}, {'name': 'B', 'max_score': 5}]}]},
     'müssen die Höchstpunkte der Kategorie (20) ergeben'),
    ({'passing_percent': 120}, 'Bestehensgrenze'),
])
def test_vorlage_pruefung(ex, change, message):
    res = ex['lea'].post('/api/assessment-templates', json={**TEMPLATE, 'name': 'Neu', **change})
    assert res.status_code == 400 and message in res.get_json()['error'], res.get_json()


def test_startvorlage_aus_migration_erfuellt_die_regeln(ex):
    seed = _load_migration('0009_assessments.py').SEED_TEMPLATE
    body = {'name': seed['name'] + ' Test', 'passing_percent': seed['passing_percent'], 'categories': [
        {'name': n, 'max_score': m, 'weight': w, 'passing_score': p,
         'criteria': [{'name': c, 'max_score': m / len(crit)} for c in crit]}
        for n, m, w, p, crit in seed['categories']]}
    res = ex['lea'].post('/api/assessment-templates', json=body)
    assert res.status_code == 201, res.get_json()
    assert res.get_json()['max_total'] == 130


def test_vorlage_gesperrt_sobald_benutzt_kopie_wieder_frei(ex):
    tid = ex['tpl']['id']
    assert ex['lea'].patch(f'/api/assessment-templates/{tid}', json={'passing_percent': 70}).status_code == 200
    _create(ex)
    assert ex['lea'].get(f'/api/assessment-templates/{tid}').get_json()['locked'] is True
    res = ex['lea'].patch(f'/api/assessment-templates/{tid}', json={'passing_percent': 50})
    assert res.status_code == 409 and 'gesperrt' in res.get_json()['error']
    assert ex['lea'].patch(f'/api/assessment-templates/{tid}', json={'name': 'Umbenannt'}).status_code == 200
    copy = ex['lea'].post(f'/api/assessment-templates/{tid}/copy').get_json()
    assert copy['name'] == 'Umbenannt (Kopie)' and copy['locked'] is False and copy['passing_percent'] == 70
    assert [c['name'] for c in copy['categories']] == ['Lesen', 'Sprechen']
    assert ex['lea'].patch(f'/api/assessment-templates/{copy["id"]}', json={'passing_percent': 50}).status_code == 200


def test_archivierte_vorlage_nicht_mehr_waehlbar(ex):
    ex['lea'].post(f'/api/assessment-templates/{ex["tpl"]["id"]}/archive')
    res = ex['maria'].post('/api/assessments', json={'trainee_id': ex['budi'], 'template_id': ex['tpl']['id'],
                                                     'assessed_on': TODAY})
    assert res.status_code == 400 and res.get_json()['field'] == 'template_id'


# ---------- Berechnung ----------

def test_berechnung_gewichtet_und_mindestpunkte_je_kategorie(ex):
    aid = _create(ex, scores=_scores(ex, 16, [3, 3, 3, 3, 2.5]))
    res = ex['maria'].post(f'/api/assessments/{aid}/finalize')
    assert res.status_code == 200, res.get_json()
    result = res.get_json()['result']
    lesen, sprechen = result['categories']
    assert (lesen['score'], lesen['percent'], lesen['passed']) == (16, 80.0, True)
    assert (sprechen['score'], sprechen['percent'], sprechen['passed']) == (14.5, 58.0, False)
    assert (lesen['weighted'], sprechen['weighted']) == (26.7, 38.7)
    # (80 * 1 + 58 * 2) / 3 = 65,33 -> 65,3 — ueber 60 %, aber Sprechen unter der Mindestpunktzahl
    assert (result['overall_percent'], result['passed']) == (65.3, False)
    stored = res.get_json()['assessment']
    assert (stored['status'], stored['overall_percent'], stored['passed']) == ('FINAL', 65.3, False)


def test_vorschau_rechnet_wie_der_server(ex):
    scores = _scores(ex, 18, [4, 4, 4, 4, 4])
    preview = ex['maria'].post(f'/api/assessment-templates/{ex["tpl"]["id"]}/evaluate', json={'scores': scores})
    aid = _create(ex, scores=scores)
    final = ex['maria'].post(f'/api/assessments/{aid}/finalize').get_json()
    assert preview.get_json() == final['result']
    assert final['assessment']['overall_percent'] == preview.get_json()['overall_percent'] == 83.3


def test_entwurf_darf_unvollstaendig_sein_abschluss_nicht(ex):
    aid = _create(ex, scores=[{'category_id': ex['lesen'], 'points': 10}])
    body = ex['maria'].get(f'/api/assessments/{aid}').get_json()
    assert body['assessment']['status'] == 'DRAFT' and body['result']['complete'] is False
    assert body['result']['overall_percent'] is None and body['assessment']['overall_percent'] is None
    res = ex['maria'].post(f'/api/assessments/{aid}/finalize')
    assert res.status_code == 400 and 'Sprechen' in res.get_json()['error']
    later = (today() + timedelta(days=3)).isoformat()
    res = ex['maria'].post(f'/api/assessments/{aid}/finalize',
                           json={'assessed_on': later, 'scores': _scores(ex, 10, [3, 3, 3, 3, 3])})
    assert res.status_code == 400 and res.get_json()['field'] == 'assessed_on'


@pytest.mark.parametrize('score', [
    {'points': 21}, {'points': -1}, {'points': 3.3}, {'category_id': 99999, 'points': 1},
])
def test_ungueltige_punkte(ex, score):
    item = {'category_id': ex['lesen'], **score}
    res = ex['maria'].post('/api/assessments', json={'trainee_id': ex['budi'], 'template_id': ex['tpl']['id'],
                                                     'assessed_on': TODAY, 'scores': [item]})
    assert res.status_code == 400 and res.get_json()['field'] == 'scores'


def test_punkte_einer_kategorie_mit_unterkategorien_nur_ueber_diese(ex):
    sprechen = ex['tpl']['categories'][1]['id']
    res = ex['maria'].post('/api/assessments', json={'trainee_id': ex['budi'], 'template_id': ex['tpl']['id'],
                                                     'assessed_on': TODAY,
                                                     'scores': [{'category_id': sprechen, 'points': 20}]})
    assert res.status_code == 400


def test_korrektur_neu_berechnet_und_protokolliert(ex):
    aid = _create(ex, scores=_scores(ex, 16, [3, 3, 3, 3, 2.5]))
    ex['maria'].post(f'/api/assessments/{aid}/finalize')
    res = ex['maria'].patch(f'/api/assessments/{aid}', json={
        'scores': [{'criterion_id': ex['crit'][4], 'points': 3}], 'reason': 'Tippfehler'})
    body = res.get_json()
    assert (body['assessment']['overall_percent'], body['assessment']['passed']) == (66.7, True)
    log = ex['admin'].get('/api/activity').get_json()['activity'][0]
    assert log['action'] == 'assessment.correct' and log['reason'] == 'Tippfehler'
    assert log['summary'] == 'Bewertung geändert: Budi – Testvorlage: 65,3 % → 66,7 %'
    assert log['detail']['changes']['Sprechen – Interaktion'] == [2.5, 3.0]
    assert log['detail']['changes']['Bestanden'] == [False, True]
    # abgeschlossene bleiben vollstaendig
    res = ex['maria'].patch(f'/api/assessments/{aid}', json={'scores': [{'category_id': ex['lesen'], 'points': None}]})
    assert res.status_code == 400


def test_entwurf_verwerfen_abgeschlossene_nie(ex):
    draft = _create(ex)
    assert ex['maria'].delete(f'/api/assessments/{draft}').status_code == 200
    final = _create(ex, scores=_scores(ex, 10, [3, 3, 3, 3, 3]))
    ex['maria'].post(f'/api/assessments/{final}/finalize')
    assert ex['maria'].delete(f'/api/assessments/{final}').status_code == 409


# ---------- Reichweite + Rechte ----------

def test_dozent_nur_eigene_kandidaten_und_immer_selbst_pruefer(ex):
    res = ex['maria'].post('/api/assessments', json={'trainee_id': ex['dewi'], 'template_id': ex['tpl']['id'],
                                                     'assessed_on': TODAY})
    assert res.status_code == 400 and res.get_json()['field'] == 'trainee_id'
    res = ex['maria'].post('/api/assessments', json={'trainee_id': ex['budi'], 'template_id': ex['tpl']['id'],
                                                     'assessed_on': TODAY, 'instructor_id': ex['ids']['tom']})
    assert res.status_code == 400 and res.get_json()['field'] == 'instructor_id'
    aid = _create(ex)
    assert ex['maria'].get(f'/api/assessments/{aid}').get_json()['assessment']['instructor']['name'] == 'Maria'
    assert ex['tom'].get(f'/api/assessments/{aid}').status_code == 404            # Budi nicht in Toms Kurs
    assert [a['id'] for a in ex['tom'].get('/api/assessments').get_json()['assessments']] == []


def test_nur_pruefer_oder_studienleitung_aendern(ex):
    ex['admin'].post(f'/api/courses/{ex["k2"]}/participants', json={'trainee_ids': [ex['budi']]})
    aid = _create(ex)
    assert ex['tom'].get(f'/api/assessments/{aid}').status_code == 200             # sieht Budi jetzt
    res = ex['tom'].patch(f'/api/assessments/{aid}', json={'strengths': 'x'})
    assert res.status_code == 403 and 'Prüfer' in res.get_json()['error']
    assert ex['lea'].patch(f'/api/assessments/{aid}', json={'strengths': 'Gut'}).status_code == 200


def test_studienleitung_waehlt_pruefer(ex):
    res = ex['lea'].post('/api/assessments', json={'trainee_id': ex['dewi'], 'template_id': ex['tpl']['id'],
                                                   'assessed_on': TODAY})
    assert res.status_code == 400 and res.get_json()['field'] == 'instructor_id'
    aid = _create(ex, client='lea', trainee='dewi', instructor_id=ex['ids']['tom'], course_id=ex['k2'])
    body = ex['tom'].get(f'/api/assessments/{aid}').get_json()
    assert body['assessment']['course']['name'] == 'Kurs Tom' and body['can_edit'] is True
    res = ex['lea'].post('/api/assessments', json={'trainee_id': ex['dewi'], 'template_id': ex['tpl']['id'],
                                                   'assessed_on': TODAY, 'instructor_id': ex['ids']['tom'],
                                                   'course_id': ex['k1']})
    assert res.status_code == 400 and res.get_json()['field'] == 'course_id'      # Dewi nicht in Kurs Maria


@pytest.mark.parametrize('role,lesen,anlegen,vorlage', [
    ('HR', 200, 403, 403), ('MANAGEMENT', 200, 403, 403), ('INSTRUCTOR', 200, 400, 403),
    ('ACADEMIC_MANAGER', 200, 400, 201),
])
def test_rechte(ex, as_user, grant, role, lesen, anlegen, vorlage):
    grant('person', role)
    client = as_user('person')
    assert client.get('/api/assessments').status_code == lesen
    res = client.post('/api/assessments', json={'trainee_id': ex['dewi'], 'template_id': ex['tpl']['id'],
                                                'assessed_on': TODAY})
    assert res.status_code == anlegen        # 400: darf grundsaetzlich, aber Kandidat/Pruefer fehlt
    assert client.post('/api/assessment-templates', json={**TEMPLATE, 'name': 'X'}).status_code == vorlage


# ---------- Kandidat: nur Abgeschlossenes, nie die interne Notiz ----------

def test_kandidat_sieht_nur_abgeschlossene_ohne_interne_notiz(ex, as_user):
    texts = {'strengths': 'Gute Aussprache', 'improvements': 'Perfekt üben', 'recommendations': 'Modul 7',
             'general_feedback': 'Weiter so', 'internal_note': 'GEHEIM-INTERN'}
    final = _create(ex, scores=_scores(ex, 18, [4, 4, 4, 4, 4]), **texts)
    ex['maria'].post(f'/api/assessments/{final}/finalize')
    _create(ex, internal_note='GEHEIM-ENTWURF')
    budi = as_user('budi')
    res = budi.get('/api/my-assessments')
    raw = res.get_data(as_text=True)
    assert 'GEHEIM' not in raw and 'internal_note' not in raw and 'created_by' not in raw
    items = res.get_json()['assessments']
    assert len(items) == 1 and items[0]['overall_percent'] == 83.3 and items[0]['strengths'] == 'Gute Aussprache'
    assert [c['name'] for c in items[0]['categories']] == ['Lesen', 'Sprechen']
    assert as_user('sari').get('/api/my-assessments').get_json()['assessments'] == []
    for url in ('/api/assessments', f'/api/assessments/{final}', '/api/assessment-templates'):
        assert budi.get(url).status_code == 403, url
    assert ex['maria'].get(f'/api/assessments/{final}').get_json()['assessment']['internal_note'] == 'GEHEIM-INTERN'


def test_verlauf_im_profil_chronologisch_und_offene_in_mein_unterricht(ex):
    old = _create(ex, assessed_on=(today() - timedelta(days=30)).isoformat(), scores=_scores(ex, 12, [3] * 5))
    ex['maria'].post(f'/api/assessments/{old}/finalize')
    _create(ex)
    history = ex['lea'].get(f'/api/candidates/{ex["budi"]}').get_json()['assessments']
    assert [(a['status'], a['overall_percent']) for a in history] == [('FINAL', 60.0), ('DRAFT', None)]
    teaching = ex['maria'].get('/api/my-teaching').get_json()
    assert teaching['stats']['open_assessment_count'] == 1
    assert teaching['open_assessments'][0]['trainee']['name'] == 'Budi'
    assert ex['tom'].get('/api/my-teaching').get_json()['stats']['open_assessment_count'] == 0


def test_gespeichertes_ergebnis_entspricht_immer_der_berechnung(ex, db):
    """Invariante: nur scoring.py schreibt das Ergebnis — Neuberechnung ergibt dasselbe."""
    from app.models.assessment import Assessment
    from app.services import scoring
    for lesen, sprechen in ((20, [5] * 5), (0, [0] * 5), (11.5, [2.5, 3, 3.5, 4, 1])):
        aid = _create(ex, scores=_scores(ex, lesen, sprechen))
        ex['maria'].post(f'/api/assessments/{aid}/finalize')
    rows = Assessment.query.filter_by(status='FINAL').all()
    assert len(rows) == 3
    for row in rows:
        result = scoring.evaluate(row.template, row.points())
        assert (float(row.overall_percent), row.passed) == (result['overall_percent'], result['passed'])

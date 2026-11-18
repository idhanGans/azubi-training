"""Bewertungs-Historie: jede Aenderung an einer abgeschlossenen Bewertung nennt wer, wann, Alt und Neu
(Verlauf + an der Bewertung sichtbar) — und still, also an Korrektur und Protokoll vorbei, aendert sich
nichts: die Datenbank lehnt es ab."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from tests.test_assessments import _create, _scores, ex  # noqa: F401 (Fixture)


@pytest.fixture
def final(ex):
    """Abgeschlossene Bewertung von Budi durch Maria: 65,3 %, nicht bestanden."""
    aid = _create(ex, scores=_scores(ex, 16, [3, 3, 3, 3, 2.5]))
    assert ex['maria'].post(f'/api/assessments/{aid}/finalize').status_code == 200
    return aid


def test_korrektur_mit_wer_wann_alt_neu_grund_an_der_bewertung(ex, final, db):
    res = ex['lea'].patch(f'/api/assessments/{final}', json={
        'scores': [{'criterion_id': ex['crit'][4], 'points': 3}], 'reason': 'Tippfehler in Interaktion'})
    assert res.status_code == 200
    body = res.get_json()
    assert (body['assessment']['overall_percent'], body['assessment']['passed']) == (66.7, True)
    assert body['assessment']['updated_by'] == 'lea' and body['assessment']['updated_at']
    created, finalized, corrected = body['history']
    assert [created['action'], finalized['action'], corrected['action']] == [
        'assessment.create', 'assessment.finalize', 'assessment.correct']
    assert (created['actor'], finalized['actor'], corrected['actor']) == ('maria', 'maria', 'lea')
    assert created['actor_name'] == 'Maria' and corrected['created_at'] >= finalized['created_at']
    assert corrected['reason'] == 'Tippfehler in Interaktion'
    assert {c['field']: [c['old'], c['new']] for c in corrected['changes']} == {
        'Sprechen – Interaktion': [2.5, 3.0], 'Gesamt': [65.3, 66.7], 'Bestanden': [False, True]}
    # dasselbe steht im (unveraenderlichen) Verlauf
    entry = db.session.execute(text("SELECT actor, reason FROM activity_log WHERE action = 'assessment.correct'")).one()
    assert tuple(entry) == ('lea', 'Tippfehler in Interaktion')
    # der Verlauf ist fuer jeden sichtbar, der die Bewertung sehen darf — nicht fuer andere
    assert len(ex['maria'].get(f'/api/assessments/{final}').get_json()['history']) == 3
    assert ex['tom'].get(f'/api/assessments/{final}').status_code == 404


@pytest.mark.parametrize('reason', [None, '', '   '])
def test_korrektur_nur_mit_grund(ex, final, db, reason):
    body = {'scores': [{'criterion_id': ex['crit'][4], 'points': 3}]}
    if reason is not None:
        body['reason'] = reason
    res = ex['lea'].patch(f'/api/assessments/{final}', json=body)
    assert res.status_code == 400 and res.get_json()['field'] == 'reason'
    after = ex['lea'].get(f'/api/assessments/{final}').get_json()
    assert after['assessment']['overall_percent'] == 65.3                          # nichts gespeichert
    assert [h['action'] for h in after['history']] == ['assessment.create', 'assessment.finalize']


def test_pruefer_und_kurs_nach_abschluss_fest(ex, final):
    """Nur im Entwurf waehlbar — nach dem Abschluss aendert ein PATCH sie nicht (und protokolliert nichts)."""
    ex['lea'].patch(f'/api/assessments/{final}', json={'instructor_id': ex['ids']['tom']})
    body = ex['lea'].get(f'/api/assessments/{final}').get_json()
    assert body['assessment']['instructor']['name'] == 'Maria'
    assert [h['action'] for h in body['history']] == ['assessment.create', 'assessment.finalize']


def test_ohne_aenderung_kein_eintrag_und_kandidat_sieht_keinen_verlauf(ex, final, as_user):
    ex['maria'].patch(f'/api/assessments/{final}', json={'scores': _scores(ex, 16, [3, 3, 3, 3, 2.5])})
    assert [h['action'] for h in ex['maria'].get(f'/api/assessments/{final}').get_json()['history']] == [
        'assessment.create', 'assessment.finalize']
    mine = as_user('budi').get('/api/my-assessments').get_json()
    assert 'history' not in mine['assessments'][0] and 'internal_note' not in mine['assessments'][0]


def test_nur_pruefer_oder_studienleitung(ex, final, as_user):
    assert ex['tom'].patch(f'/api/assessments/{final}', json={'reason': 'x'}).status_code == 404
    assert as_user('budi').patch(f'/api/assessments/{final}', json={'reason': 'x'}).status_code == 403


STILL = [
    ('Ergebnis', 'UPDATE assessment SET overall_percent = 99 WHERE id = :a'),
    ('Bestanden', 'UPDATE assessment SET passed = true WHERE id = :a'),
    ('zurueck auf Entwurf', "UPDATE assessment SET status = 'DRAFT', overall_percent = NULL, passed = NULL WHERE id = :a"),
    ('anderer Kandidat', 'UPDATE assessment SET trainee_id = trainee_id + 1 WHERE id = :a'),
    ('loeschen', 'DELETE FROM assessment WHERE id = :a'),
    ('Punkte aendern', 'UPDATE assessment_score SET points = 1 WHERE assessment_id = :a'),
    ('Punkte entfernen', 'DELETE FROM assessment_score WHERE assessment_id = :a'),
    ('Punkte dazu', 'INSERT INTO assessment_score (assessment_id, category_id, points) '
                    'SELECT :a, id, 1 FROM assessment_category WHERE template_id = :t AND name = \'Sprechen\''),
    ('Bestehensgrenze', 'UPDATE assessment_template SET passing_percent = 10 WHERE id = :t'),
    ('Hoechstpunkte', 'UPDATE assessment_category SET max_score = 40 WHERE template_id = :t AND name = \'Lesen\''),
    ('Gewicht', 'UPDATE assessment_category SET weight = 5 WHERE template_id = :t'),
    ('Kategorie dazu', "INSERT INTO assessment_category (template_id, name, max_score, weight, position) "
                       "VALUES (:t, 'Neu', 10, 1, 9)"),
    ('Unterkategorie', 'UPDATE assessment_criterion SET max_score = 9 WHERE id = :c'),
]


@pytest.mark.parametrize('what,sql', STILL, ids=[w for w, _ in STILL])
def test_still_aendern_lehnt_die_datenbank_ab(ex, final, db, what, sql):
    with pytest.raises(ProgrammingError, match='nur ueber die Korrektur'):
        db.session.execute(text(sql), {'a': final, 't': ex['tpl']['id'], 'c': ex['crit'][0]})
    db.session.rollback()


def test_erlaubt_bleibt_was_kein_ergebnis_aendert(ex, final, db):
    draft = _create(ex, trainee='sari', scores=_scores(ex, 10, [1, 1, 1, 1, 1]))
    params = {'a': final, 't': ex['tpl']['id']}
    db.session.execute(text("UPDATE assessment SET general_feedback = 'Text' WHERE id = :a"), params)
    db.session.execute(text("UPDATE assessment_category SET skill = 'READING' WHERE template_id = :t "
                            "AND name = 'Lesen'"), params)
    db.session.execute(text('UPDATE assessment_score SET points = 2 WHERE assessment_id = :d'), {'d': draft})
    db.session.execute(text("SET LOCAL azubi.assessment_correction = 'on'"))       # wie Korrektur/Abschluss
    db.session.execute(text('UPDATE assessment SET overall_percent = 70 WHERE id = :a'), params)
    db.session.rollback()
    # Entwurf verwerfen bleibt moeglich
    assert ex['maria'].delete(f'/api/assessments/{draft}').status_code == 200

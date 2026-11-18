"""/docs-Eintraege fuer Bewertungsvorlagen und Bewertungen (Phase 7)."""
_CAT = {'id': 4, 'name': 'Sprechen', 'description': None, 'max_score': 25.0, 'weight': 1.0, 'passing_score': 15.0,
        'position': 3, 'criteria': [{'id': 6, 'name': 'Aussprache', 'max_score': 5.0, 'position': 0}]}
_TPL = {'id': 1, 'name': 'B1 Monatsbewertung', 'description': 'Alle sechs Fertigkeiten',
        'level_id': 3, 'level': {'id': 3, 'code': 'B1', 'name': 'B1'}, 'passing_percent': 60.0,
        'categories': [_CAT], 'max_total': 130.0, 'usage_count': 12, 'locked': True, 'archived_at': None}
_TPL_IN = {'name': 'B1 Monatsbewertung', 'level_id': 3, 'passing_percent': 60,
           'categories': [{'name': 'Lesen', 'max_score': 20, 'weight': 1, 'passing_score': 12},
                          {'name': 'Sprechen', 'max_score': 25, 'weight': 1, 'passing_score': 15,
                           'criteria': [{'name': 'Aussprache', 'max_score': 5}, {'name': 'Flüssigkeit', 'max_score': 5},
                                        {'name': 'Wortschatz', 'max_score': 5}, {'name': 'Grammatik', 'max_score': 5},
                                        {'name': 'Interaktion', 'max_score': 5}]}]}
_RESULT = {'complete': True, 'overall_percent': 74.5, 'passed': True, 'passing_percent': 60.0,
           'categories': [{'id': 4, 'name': 'Sprechen', 'max_score': 25.0, 'weight': 1.0, 'passing_score': 15.0,
                           'score': 18.5, 'points_so_far': 18.5, 'percent': 74.0, 'weighted': 12.3, 'passed': True,
                           'criteria': [{'id': 6, 'name': 'Aussprache', 'max_score': 5.0, 'points': 3.5}]}]}
_SUMMARY = {'id': 9, 'assessed_on': '2026-09-25', 'status': 'FINAL', 'overall_percent': 74.5, 'passed': True,
            'trainee': {'id': 5, 'candidate_no': 'K-00005', 'name': 'Budi Santoso', 'archived': False},
            'template': {'id': 1, 'name': 'B1 Monatsbewertung', 'archived': False},
            'instructor': {'id': 2, 'name': 'Nina', 'status': 'ACTIVE', 'archived': False},
            'course': {'id': 1, 'name': 'B1 – Gruppe Herbst'}, 'finalized_at': '2026-09-25T09:12:00+00:00'}
_FEEDBACK = {'strengths': 'Spricht flüssig', 'improvements': 'Perfekt-Formen', 'recommendations': 'Modul 7 wiederholen',
             'general_feedback': 'Gute Entwicklung'}
_DETAIL = {'assessment': {**_SUMMARY, **_FEEDBACK, 'internal_note': 'Nur intern',
                          'scores': [{'category_id': None, 'criterion_id': 6, 'points': 3.5}]},
           'template': _TPL, 'result': _RESULT, 'can_edit': True,
           # Verlauf dieser Bewertung (Anlegen, Abschluss, Korrekturen) — wer, wann, Alt -> Neu, Grund
           'history': [{'created_at': '2026-09-25T10:00:00+00:00', 'actor': 'lea', 'actor_name': 'Lea',
                        'action': 'assessment.correct', 'summary': 'Bewertung geändert: Budi – B1: 65,3 % → 66,7 %',
                        'changes': [{'field': 'Sprechen – Interaktion', 'old': 2.5, 'new': 3.0},
                                    {'field': 'Gesamt', 'old': 65.3, 'new': 66.7}], 'reason': 'Tippfehler'}]}
_SCORES = {'scores': [{'category_id': 1, 'points': 16}, {'criterion_id': 6, 'points': 3.5}]}


def _e(method, path, description, response, request=None):
    entry = {'path': path, 'method': method, 'description': description, 'response_example': response}
    if request is not None:
        entry['request_example'] = request
    return entry


DOCS = [
    _e('GET', '/api/assessment-templates', 'Bewertungsvorlagen (?archived=1 archivierte) mit Kategorien, '
       'Unterkategorien, Nutzung und Sperre (`locked`, sobald benutzt), dazu der Vorschlag für die Bestehensgrenze '
       'neuer Vorlagen — assessment.view', {'templates': [_TPL], 'default_passing_percent': 60}),
    _e('GET', '/api/assessment-templates/<id>', 'Eine Vorlage — assessment.view', _TPL),
    _e('POST', '/api/assessment-templates', 'Vorlage anlegen. Kategorie mit Unterkategorien: max_score = Summe '
       'der Unterkategorien; Punkte in 0,5er-Schritten; Gewicht > 0 — assessment.configure', _TPL, _TPL_IN),
    _e('PATCH', '/api/assessment-templates/<id>', 'Vorlage ändern: Name/Beschreibung/Niveau immer; Struktur '
       '(categories, passing_percent) nur solange ungenutzt, sonst 409 — assessment.configure', _TPL,
       {'name': 'B1 Monatsbewertung', 'passing_percent': 65}),
    _e('POST', '/api/assessment-templates/<id>/copy', 'Als neue Version kopieren (Name optional, sonst '
       '„… (Kopie)“); die Kopie ist wieder änderbar — assessment.configure', {**_TPL, 'id': 2, 'locked': False},
       {'name': 'B1 Monatsbewertung 2027'}),
    _e('POST', '/api/assessment-templates/<id>/archive', 'Archivieren (keine neuen Bewertungen mehr, bestehende '
       'bleiben) — assessment.configure', _TPL, {}),
    _e('POST', '/api/assessment-templates/<id>/restore', 'Wiederherstellen — assessment.configure', _TPL, {}),
    _e('POST', '/api/assessment-templates/<id>/evaluate', 'Vorschau-Berechnung für eingegebene Punkte (schreibt '
       'nichts) — dieselbe Rechenstelle wie beim Speichern — assessment.view', _RESULT, _SCORES),
    _e('GET', '/api/assessments', 'Bewertungen (neueste zuerst), seitenweise page (ab 1) + per_page (Standard 50, '
       'max. 200); Filter trainee_id, template_id, instructor_id, course_id, status (DRAFT|FINAL), mine=1 — '
       'assessment.view; Dozenten: nur Kandidaten ihrer Kurse',
       {'assessments': [_SUMMARY], 'total': 1, 'page': 1, 'per_page': 50}),
    _e('POST', '/api/assessments', 'Bewertung als Entwurf anlegen (Punkte optional). Dozenten sind immer selbst '
       'Prüfer; Studienleitung wählt instructor_id — assessment.create', {**_DETAIL, 'can_edit': True},
       {'trainee_id': 5, 'template_id': 1, 'assessed_on': '2026-09-25', 'course_id': 1, **_SCORES}),
    _e('GET', '/api/assessments/<id>', 'Bewertung mit Vorlage, Punkten, berechnetem Ergebnis, Feedback und '
       'interner Notiz — assessment.view', _DETAIL),
    _e('PATCH', '/api/assessments/<id>', 'Punkte/Feedback/interne Notiz/Datum speichern (Entwurf: auch Prüfer, '
       'Kurs; points=null entfernt einen Wert). Abgeschlossene: Korrektur, Ergebnis wird neu berechnet und mit '
       'Alt → Neu protokolliert, Pflicht: reason (Grund, sonst 400) — assessment.edit, nur Prüfer oder Studienleitung',
       _DETAIL, {**_SCORES, **_FEEDBACK, 'internal_note': 'Nur intern'}),
    _e('POST', '/api/assessments/<id>/finalize', 'Abschließen (optional mit denselben Feldern wie PATCH): alle '
       'Punkte nötig, Datum nicht in der Zukunft; speichert Gesamt + Bestanden; danach für den Kandidaten '
       'sichtbar — assessment.edit', _DETAIL, _SCORES),
    _e('DELETE', '/api/assessments/<id>', 'Entwurf verwerfen (abgeschlossene: 409) — assessment.edit',
       {'deleted': 9}, {}),
    _e('GET', '/api/my-assessments', 'Kandidat: eigene ABGESCHLOSSENE Bewertungen (älteste zuerst) mit '
       'Kategorie-Ergebnissen und Feedback — ohne interne Notiz',
       {'assessments': [{'id': 9, 'assessed_on': '2026-09-25', 'overall_percent': 74.5, 'passed': True,
                         'template': {'id': 1, 'name': 'B1 Monatsbewertung'}, 'instructor': {'name': 'Nina'},
                         'course': {'name': 'B1 – Gruppe Herbst'}, **_FEEDBACK,
                         'categories': _RESULT['categories']}]}),
]

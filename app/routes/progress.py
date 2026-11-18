"""Fortschritt: Fertigkeiten, Bewertungs-Verlauf, Module, Anwesenheit je Woche.

Team: nur Kandidaten in Reichweite (`scope`), Teile je nach Recht
(`assessment.view`, `attendance.view`). Kandidat: nur sich selbst.
Gerechnet wird in `app/services/progress.py`.
"""
from flask import Blueprint, jsonify

from app import auth
from app.extensions import db
from app.models.trainee import Trainee
from app.services import progress, scope, validation as v

bp = Blueprint('progress', __name__, url_prefix='/api')


@bp.route('/candidates/<int:cid>/progress', methods=['GET'])
@auth.require_permission('candidate.view')
def candidate_progress(cid):
    identity = auth.current_identity()
    if db.session.get(Trainee, cid) is None or not scope.can_see_trainee(identity, cid):
        raise v.NotFound('Kandidat nicht gefunden.')
    return jsonify(progress.overview(cid, scope.course_condition(identity),
                                     with_assessments=identity.can('assessment.view'),
                                     with_attendance=identity.can('attendance.view')))


@bp.route('/my-progress', methods=['GET'])
@auth.candidate_only
def my_progress():
    """Kandidat: eigener Fortschritt (nur abgeschlossene Bewertungen, keine internen Notizen)."""
    return jsonify(progress.overview(auth.current_identity().trainee_id))


_SKILL = {'skill': 'SPEAKING', 'current': 69.0, 'current_date': '2026-09-19', 'first': 58.0, 'change': 11.0,
          'count': 4, 'series': [{'assessment_id': 3, 'date': '2026-08-19', 'template': 'Einstufungstest',
                                  'percent': 58.0}]}
_BODY = {
    'skills': [_SKILL],
    'assessment_trend': [{'assessment_id': 3, 'date': '2026-08-19', 'template': 'Einstufungstest',
                          'overall_percent': 62.0, 'passed': True}],
    'modules': [{'curriculum': {'id': 1, 'program': 'Deutsch für Azubis – Sprechkurs',
                                'level': {'id': 3, 'code': 'B1', 'name': 'B1'}},
                 'course': {'id': 1, 'name': 'Sprechkurs B1 – Gruppe Nina', 'status': 'RUNNING'},
                 'current': {'id': 7, 'name': 'Modul 7 – Fehler & Probleme'}, 'completed': 6, 'total': 18,
                 'percent': 33.3, 'items': [{'id': 1, 'name': 'Modul 1 – Ankommen in Deutschland', 'state': 'done'}]}],
    'attendance': {'stats': {'present': 15, 'late': 2, 'excused': 1, 'absent': 1, 'recorded': 19, 'rate': 0.9444},
                   'weeks': [{'week_start': '2026-09-14', 'present': 2, 'late': 0, 'excused': 0, 'absent': 0,
                              'rate': 1.0}]},
}

DOCS = [
    {'path': '/api/candidates/<id>/progress', 'method': 'GET',
     'description': 'Fortschritt eines Kandidaten: Fertigkeiten (aktueller Stand = neueste abgeschlossene Bewertung, '
                    'Veränderung zur ersten), Verlauf der Gesamtergebnisse, Module je Curriculum (abgeschlossen = vor '
                    'dem aktuellen Kursmodul), Anwesenheit je Woche — candidate.view; skills/assessment_trend nur mit '
                    'assessment.view, attendance nur mit attendance.view; Dozenten: nur Kandidaten ihrer Kurse (404), '
                    'Module/Anwesenheit nur aus ihren Kursen',
     'response_example': _BODY},
    {'path': '/api/my-progress', 'method': 'GET',
     'description': 'Kandidat: eigener Fortschritt (gleicher Aufbau, nur abgeschlossene Bewertungen)',
     'response_example': _BODY},
]

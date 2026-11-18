"""Team-Dashboard: Kennzahlen + Handlungsbedarf je Rolle (Definitionen: `app/services/dashboard.py`)."""
from flask import Blueprint, jsonify

from app import auth
from app.services import dashboard

bp = Blueprint('dashboard', __name__, url_prefix='/api')


@bp.route('/dashboard', methods=['GET'])
@auth.require_permission('candidate.view')
def get_dashboard():
    return jsonify(dashboard.overview(auth.current_identity()))


_REF = {'id': 5, 'candidate_no': 'K-00005', 'name': 'Budi Santoso'}
DOCS = [
    {'path': '/api/dashboard', 'method': 'GET',
     'description': 'Team-Dashboard in der eigenen Reichweite (Dozenten: nur eigene Kurse): Kandidaten, aktive '
                    'Kandidaten (in laufendem Kurs), Ø neueste abgeschlossene Bewertung je Kandidat, Anwesenheit '
                    '(alle zählbaren Einträge zusammen), Module abgeschlossen, offene Bewertungen; Verteilung nach '
                    'Status/Niveau; Handlungsbedarf nur mit passendem Recht (assessment.edit, attendance.manage, '
                    'attendance.view, schedule.edit, candidate.edit) — candidate.view',
     'response_example': {
         'scope': 'all',
         'kpis': {'candidates': 128, 'active_candidates': 96, 'avg_assessment': 78.4, 'assessed_candidates': 90,
                  'attendance': {'present': 900, 'late': 40, 'excused': 20, 'absent': 84, 'recorded': 1044,
                                 'rate': 0.918},
                  'modules_completed': 72.0, 'modules': {'completed': 1296, 'total': 1800}, 'open_assessments': 8},
         'by_status': [{'label': 'Im Sprachkurs', 'count': 96}, {'label': None, 'count': 4}],
         'by_level': [{'label': 'A2', 'count': 40}, {'label': 'B1', 'count': 80}],
         'attention': {'open_assessments': {'count': 8},
                       'open_attendance': {'count': 1, 'days': 14, 'items': [{'id': 7, 'date': '2026-09-24',
                                                                             'start': '09:00', 'end': '11:00'}]},
                       'low_attendance': {'count': 1, 'below_percent': 80, 'items': [{**_REF, 'rate': 0.62}]},
                       'without_course': {'count': 1, 'items': [_REF]},
                       'incomplete_profile': {'count': 1, 'items': [{**_REF, 'missing': ['status']}]}}}},
]

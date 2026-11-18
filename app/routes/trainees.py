"""Team: Kennzahlen je Kandidat fuers Trainings-Monitoring.

Anlegen/Aendern/Archivieren liegt in routes/candidates.py.
"""
from flask import Blueprint, jsonify

from app import auth
from app.services import scope, training_stats

bp = Blueprint('trainees', __name__, url_prefix='/api/trainees')


@bp.route('', methods=['GET'])
@auth.require_permission('candidate.view')
def list_trainees():
    return jsonify({'trainees': training_stats.trainee_overview(
        visible=scope.trainee_ids(auth.current_identity()))})


DOCS = [
    {'path': '/api/trainees', 'method': 'GET',
     'description': 'Aktive Kandidaten mit Trainings-Kennzahlen (Stunden, Tage, Bewertungs-Mittel) — candidate.view; Dozenten: nur Teilnehmer eigener Kurse',
     'response_example': {'trainees': [{'id': 1, 'candidate_no': 'K-00001', 'name': 'Budi',
                                        'hours_total': 60, 'days_reported': 10, 'rating_language': 7.5}]}},
]

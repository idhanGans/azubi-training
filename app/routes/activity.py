"""Activity log (Verlauf, audit trail) — only with permission audit.view (super admin). Read-only: entries are
immutable (DB trigger, migration 0012), there is no route to change or delete them."""
from flask import Blueprint, jsonify, request

from app import auth
from app.services import activity, validation as v

bp = Blueprint('activity', __name__, url_prefix='/api')

MAX_LIMIT = 500


@bp.route('/activity', methods=['GET'])
@auth.require_permission('audit.view')
def list_activity():
    args = request.args
    entries, next_before_id = activity.search(
        entity_type=v.text(args, 'entity_type', 'entity_type', 120), actor=v.text(args, 'actor', 'actor', 120),
        action=v.text(args, 'action', 'Aktion', 80),
        entity_id=v.integer(args, 'entity_id', 'Datensatz', 1, 2**31 - 1),
        first=v.day(args, 'from', 'Von'), last=v.day(args, 'to', 'Bis'), text=v.text(args, 'q', 'Suche', 100),
        before_id=v.integer(args, 'before_id', 'Seite', 1, 2**31 - 1),
        limit=v.integer(args, 'limit', 'Anzahl', 1, MAX_LIMIT) or 100)
    return jsonify({'activity': entries, 'next_before_id': next_before_id})


@bp.route('/activity/facets', methods=['GET'])
@auth.require_permission('audit.view')
def facets():
    """Selection lists for the filters: who did something, which actions exist."""
    return jsonify(activity.facets())


_ENTRY = {'id': 812, 'actor': 'anna.mueller', 'actor_name': 'Anna Müller', 'action': 'assessment.correct',
          'entity_type': 'trainee', 'entity_id': 5, 'entity_name': 'Max Mustermann',
          'summary': 'Bewertung geändert: Max Mustermann – B1 Monatsbewertung: 82 % → 85 %',
          'detail': {'assessment_id': 9, 'changes': {'Gesamt': [82.0, 85.0], 'Lesen': [16.0, 18.0]}},
          'changes': [{'field': 'Gesamt', 'old': 82.0, 'new': 85.0}, {'field': 'Lesen', 'old': 16.0, 'new': 18.0}],
          'reason': 'Tippfehler', 'created_at': '2026-09-25T07:12:00+00:00'}
DOCS = [
    {'path': '/api/activity', 'method': 'GET',
     'description': 'Verlauf (neueste zuerst; unveränderlich). Filter: actor, action (Präfix, z.B. „assessment"), '
                    'entity_type + entity_id, from/to (JJJJ-MM-TT, Ortszeit), q (Text), limit (max. 500, Standard 100), '
                    'before_id (nächste Seite) — audit.view',
     'response_example': {'activity': [_ENTRY], 'next_before_id': 700}},
    {'path': '/api/activity/facets', 'method': 'GET',
     'description': 'Auswahllisten für die Verlaufs-Filter: Logins (mit Namen, falls Dozent/Kandidat), Aktionen, '
                    'Datensatz-Arten — '
                    'audit.view',
     'response_example': {'actors': [{'login': 'anna.mueller', 'name': 'Anna Müller'}],
                          'actions': ['assessment.correct', 'trainee.update'], 'entity_types': ['course', 'trainee']}},
]

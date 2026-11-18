"""Team: training reports (Trainings-Reports) of all participants + ratings by SPV, department leader and
internal team.

Rating (`rating.create`) and the rating overview (`rating.view`) are available to every login except
candidates; WHO they rate is decided by `services/supervision.py` (SPV: their candidates, leader: their
departments, internal team: all active ones). Only the team (`assessment.view`) reads the individual
ratings of ALL raters.
"""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.staff_rating import StaffRating
from app.models.trainee import Trainee
from app.models.training_report import TrainingReport
from app.services import audit, rating_board, scope, validation as v

bp = Blueprint('reports', __name__, url_prefix='/api')

#: Upper limit per query — the UI always queries per participant.
MAX_ROWS = 2000


@bp.route('/training', methods=['GET'])
@auth.require_permission('candidate.view')
def all_reports():
    q = scope.restrict(TrainingReport.query, TrainingReport.trainee_id, auth.current_identity())
    tid = request.args.get('trainee_id', type=int)
    if tid:
        q = q.filter_by(trainee_id=tid)
    reports = q.order_by(TrainingReport.created_at.desc()).limit(MAX_ROWS).all()
    return jsonify({'reports': [r.to_dict() for r in reports]})


@bp.route('/ratings', methods=['GET'])
@auth.require_permission('assessment.view')
def list_ratings():
    q = scope.restrict(StaffRating.query, StaffRating.trainee_id, auth.current_identity())
    tid = request.args.get('trainee_id', type=int)
    if tid:
        q = q.filter_by(trainee_id=tid)
    ratings = q.order_by(StaffRating.created_at.desc()).limit(MAX_ROWS).all()
    return jsonify({'ratings': [r.to_dict() for r in ratings]})


_KIND_TEXT = {'SPV': 'SPV-Bewertung', 'LEITER': 'Leiter-Bewertung', 'INTERN': 'Interne Bewertung'}


@bp.route('/ratings', methods=['POST'])
@auth.require_permission('rating.create')
def add_rating():
    data = request.get_json(silent=True) or {}
    found = rating_board.rateable(auth.current_identity(), data.get('trainee_id'))
    if found is None:
        raise v.ValidationError('Bitte einen Ihnen zugeordneten, aktiven Kandidaten auswählen.', 'trainee_id')
    trainee, kind = found
    values = rating_board.read_scores(data)
    month = rating_board.read_month(data, trainee, auth.actor())
    rating = StaffRating(trainee_id=trainee.id, rater=auth.actor(), kind=kind, month=month, created_by=auth.actor(),
                         **values)
    db.session.add(rating)
    db.session.flush()
    audit.log(auth.actor(), 'rating.create', entity_type='trainee', entity_id=trainee.id,
              entity_name=trainee.name, summary=f'{_KIND_TEXT[kind]} für {trainee.name}, Monat {month}: '
                                                f'{rating_board.summary_text(values)}',
              detail={'rating_id': rating.id, 'kind': kind, 'month': month, 'scores': rating.scores()})
    db.session.commit()
    return jsonify(rating.to_dict()), 201


@bp.route('/ratings/<int:rid>', methods=['PATCH'])
@auth.require_permission('rating.create')
def update_rating(rid):
    rating = db.session.get(StaffRating, rid)
    if rating is None or rating.rater != auth.actor():
        raise v.NotFound('Bewertung nicht gefunden.')
    if not rating.is_editable_by(auth.actor()):
        raise v.Forbidden('Eine Bewertung kann nur am Tag der Abgabe korrigiert werden.')
    data = request.get_json(silent=True) or {}
    before = rating.to_dict()
    for key, value in rating_board.read_scores(data).items():
        setattr(rating, key, value)
    trainee = db.session.get(Trainee, rating.trainee_id)
    audit.log(auth.actor(), 'rating.update', entity_type='trainee', entity_id=trainee.id,
              entity_name=trainee.name, summary=f'{_KIND_TEXT[rating.kind]} für {trainee.name}, Monat {rating.month}, korrigiert',
              detail={'rating_id': rating.id, 'changes': audit.diff(before, rating.to_dict())})
    db.session.commit()
    return jsonify({**rating.to_dict(), 'editable': True})


@bp.route('/rating-board', methods=['GET'])
@auth.require_permission('rating.view')
def board():
    return jsonify(rating_board.board(auth.current_identity()))


@bp.route('/rating-board/<int:tid>', methods=['GET'])
@auth.require_permission('rating.view')
def board_detail(tid):
    identity = auth.current_identity()
    found = rating_board.rateable(identity, tid)
    if found is None:
        raise v.NotFound('Kandidat nicht gefunden.')
    return jsonify(rating_board.detail(identity, *found))


_SCORES = {'r_practical': 8, 'r_reliability': 7, 'r_motivation': 9}
_STATS = {'count': 3, 'r_practical': 7.3, 'r_reliability': 8.0, 'r_motivation': 8.7, 'mean': 8.0,
          'last': '2026-10-08T03:00:00+00:00',
          'months': {'1': {'count': 2, 'r_practical': 7.0, 'r_reliability': 8.0, 'r_motivation': 8.5, 'mean': 7.83}}}
_MONTHS = {'month': 2, 'months': [1, 2], 'program_months': 3,
           'calendar': [{'month': 1, 'from': '2026-09-17', 'to': '2026-10-16', 'started': True},
                        {'month': 2, 'from': '2026-10-17', 'to': '2026-11-16', 'started': True},
                        {'month': 3, 'from': '2026-11-17', 'to': '2026-12-16', 'started': False}]}
_MINE = {'1': {'id': 7, 'kind': 'SPV', 'month': 1, **_SCORES, 'note': '…', 'editable': False}}
DOCS = [
    {'path': '/api/training', 'method': 'GET',
     'description': 'Trainings-Reports aller Teilnehmer, optional ?trainee_id= — candidate.view; Dozenten: nur eigene Kurse',
     'response_example': {'reports': []}},
    {'path': '/api/ratings', 'method': 'GET',
     'description': 'Bewertungen durch SPV/Leiter/internes Team mit Bewerter und Notiz, optional ?trainee_id= — '
                    'assessment.view (Team); Dozenten: nur eigene Kurse',
     'response_example': {'ratings': [{'id': 1, 'trainee_id': 1, 'rater': 'citra_lestari', 'kind': 'SPV', 'month': 1,
                                       **_SCORES, 'note': '…', 'created_at': '2026-10-08T03:00:00+00:00', 'updated_at': None}]}},
    {'path': '/api/ratings', 'method': 'POST',
     'description': 'Bewertung abgeben: Praktische Leistung, Zuverlässigkeit, Motivation & Verhalten je 1..10 (alle '
                    'Pflicht) + Notiz für EINEN Programm-Monat (`month` 1..3, ohne Angabe der laufende; nur begonnene Monate, '
                    'sonst 400; je Kandidat, Bewerter und Monat genau eine, sonst 409). Art ergibt sich aus der '
                    'Zuordnung: SPV des Kandidaten, Leiter seiner Abteilung, sonst internes Team (rating.internal) — '
                    'rating.create; 400 fuer nicht zugeordnete/archivierte',
     'request_example': {'trainee_id': 1, 'month': 2, **_SCORES, 'note': '…'},
     'response_example': {'id': 1, 'trainee_id': 1, 'kind': 'SPV', 'month': 2, **_SCORES, 'rater': 'citra_lestari'}},
    {'path': '/api/ratings/<id>', 'method': 'PATCH',
     'description': 'Eigene Bewertung korrigieren — nur am Tag der Abgabe (Schul-Ortszeit), sonst 403; '
                    'fremde 404. Alt/Neu im Verlauf (rating.update)',
     'request_example': {**_SCORES, 'note': '…'},
     'response_example': {'id': 1, **_SCORES, 'updated_at': '2026-10-08T05:00:00+00:00', 'editable': True}},
    {'path': '/api/rating-board', 'method': 'GET',
     'description': 'Bewertungs-Uebersicht (rating.view): die Kandidaten, die der Login bewerten darf (SPV: seine, '
                    'Leiter: seine Abteilungen, internes Team: alle aktiven) mit Art (`kind`), Abteilung, Stelle, '
                    'Gruppen und Kennzahlen des eigenen Teils (`part` spv|intern): Anzahl/Durchschnitte aller '
                    'Bewerter (gesamt = Mittel der Monate, `months` je Monat), Anzahl eigener, eigene Monate (`months_mine`) und die '
                    'EIGENE Bewertung je Monat (`mine`, `editable` = heute abgegeben); laufender Monat (`month`), '
                    'wählbare Monate (`months`), Daten jedes Programm-Monats (`calendar`) — keine Kontaktdaten, keine fremden '
                    'Einzelbewertungen',
     'response_example': {'scale': [1, 10], 'categories': list(_SCORES), 'internal': False, **_MONTHS, 'trainees': [{
         'id': 1, 'name': 'Dimas', 'nickname': None, 'abteilung': 'Bad Neuenahr – Elektro-Assistent',
         'department': {'id': 2, 'name': 'Bad Neuenahr'}, 'groups': ['Deutschkurs Gruppe 2'], 'kind': 'LEITER',
         'part': 'spv', 'stats': _STATS, 'rating_mine': 1, 'months_mine': [1], 'mine': _MINE}]}},
    {'path': '/api/rating-board/<trainee_id>', 'method': 'GET',
     'description': 'Ein bewertbarer Kandidat: Kennzahlen wie in der Uebersicht + die EIGENEN Bewertungen '
                    '(`editable` = heute abgegeben); 404 fuer nicht zugeordnete/archivierte/unbekannte',
     'response_example': {'scale': [1, 10], 'categories': list(_SCORES), **_MONTHS, 'trainee': {'id': 1, 'kind': 'SPV', 'mine': _MINE},
                          'mine': [{'id': 7, 'kind': 'SPV', 'month': 1, **_SCORES, 'note': '…', 'editable': True}]}},
]

"""Kandidaten-Sicht: der EIGENE Trainings-Report — sonst nichts.

Jede Query ist auf `identity.trainee_id` eingeschraenkt; eine fremde Report-ID
liefert 404, nicht 403 (verraet nicht, dass es sie gibt).
"""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.trainee import Trainee
from app.models.training_report import TrainingReport
from app.services import audit, training_stats, validation as v
from app.services.local_time import de_day

bp = Blueprint('my_training', __name__, url_prefix='/api/training')


def _read_report(data):
    fields = {
        'period': v.iso_date(data, 'period', 'Datum'),
        'hours': v.number(data, 'hours', 'Trainingsstunden', 0, 24),
        'lang': bool(data.get('lang')),
        'tech': bool(data.get('tech')),
        'station': v.text(data, 'station', 'Station', 120),
        'learned': v.text(data, 'learned', 'Lerninhalt', 2000),
    }
    if fields['hours'] is None and not fields['learned']:
        raise v.ValidationError('Bitte Trainingsstunden oder Lerninhalt angeben.', 'hours')
    return fields


@bp.route('/me', methods=['GET'])
@auth.candidate_only
def my_training():
    identity = auth.current_identity()
    trainee = db.session.get(Trainee, identity.trainee_id)
    reports = (TrainingReport.query.filter_by(trainee_id=trainee.id)
               .order_by(TrainingReport.created_at.desc()).all())
    return jsonify({'trainee': trainee.public_dict(), 'reports': [r.to_dict() for r in reports],
                    'summary': training_stats.report_summary(trainee.id)})


@bp.route('/me', methods=['POST'])
@auth.candidate_only
def add_my_training():
    trainee = db.session.get(Trainee, auth.current_identity().trainee_id)
    report = TrainingReport(trainee_id=trainee.id, **_read_report(request.get_json(silent=True) or {}))
    db.session.add(report)
    audit.log(auth.actor(), 'report.create', entity_type='trainee', entity_id=trainee.id,
              entity_name=trainee.name,
              summary=f'Report vom {de_day(report.period)} · {audit.de_number(report.hours or 0)} Std.')
    db.session.commit()
    return jsonify(report.to_dict()), 201


@bp.route('/me/<int:rid>', methods=['PUT'])
@auth.candidate_only
def update_my_training(rid):
    trainee = db.session.get(Trainee, auth.current_identity().trainee_id)
    report = TrainingReport.query.filter_by(id=rid, trainee_id=trainee.id).first()
    if report is None:
        return jsonify({'error': 'Report nicht gefunden.'}), 404
    if not report.is_editable():
        return jsonify({'error': 'Der Report ist älter als 7 Tage und kann nicht mehr geändert werden.'}), 403
    before = report.to_dict()
    for key, value in _read_report(request.get_json(silent=True) or {}).items():
        setattr(report, key, value)
    audit.log(auth.actor(), 'report.update', entity_type='trainee', entity_id=trainee.id,
              entity_name=trainee.name, summary=f'Report vom {de_day(report.period)} bearbeitet',
              detail={'report_id': report.id, 'changes': audit.diff(before, report.to_dict())})
    db.session.commit()
    return jsonify(report.to_dict())


_REPORT_EXAMPLE = {'period': '2026-09-16', 'hours': 6, 'lang': True, 'tech': True,
                   'station': 'Netzantrag', 'learned': '…'}

DOCS = [
    {'path': '/api/training/me', 'method': 'GET',
     'description': 'Kandidat: eigene Trainings-Reports mit Summe (Anzahl, Stunden gesamt)',
     'response_example': {'trainee': {'id': 1, 'name': 'Budi'}, 'reports': [],
                          'summary': {'report_count': 0, 'hours_total': 0.0}}},
    {'path': '/api/training/me', 'method': 'POST',
     'description': 'Kandidat: eigenen Report anlegen (400 bei ungültigen Werten)',
     'request_example': _REPORT_EXAMPLE,
     'response_example': {'id': 1, 'trainee_id': 1, 'hours': 6, 'editable': True}},
    {'path': '/api/training/me/<id>', 'method': 'PUT',
     'description': 'Kandidat: eigenen Report bearbeiten — nur bis 7 Tage nach Absenden (danach 403)',
     'request_example': _REPORT_EXAMPLE,
     'response_example': {'id': 1, 'trainee_id': 1, 'hours': 6, 'editable': True}},
]

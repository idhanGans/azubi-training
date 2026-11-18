"""Berichte: Anwesenheit, Leistung, Dozenten (Tabellen + CSV) und Kandidatenbericht — report.view.

Zeitraum `from`/`to` (Standard: letzte 90 Tage), optional `course_id`/`level_id`.
CSV: `?format=csv&table=<id>` — jeder Export wird im Verlauf protokolliert
(personenbezogene Daten verlassen die App). Rechnen: `app/services/reports.py`.
"""
from datetime import timedelta

from flask import Blueprint, Response, jsonify, request

from app import auth
from app.extensions import db
from app.models.trainee import Trainee
from app.services import audit, csv_export, reports, scope, validation as v
from app.services.local_time import de_day, today

bp = Blueprint('report_views', __name__, url_prefix='/api/reports')

DEFAULT_DAYS = 90
MAX_DAYS = 731
TITLES = {'attendance': 'Anwesenheitsbericht', 'academic': 'Leistungsbericht', 'instructors': 'Dozentenbericht'}


def _filters(args):
    last = v.day(args, 'to', 'Bis') or today()
    first = v.day(args, 'from', 'Von') or last - timedelta(days=DEFAULT_DAYS - 1)
    if first > last:
        raise v.ValidationError('„Von“ muss vor „Bis“ liegen.', 'from')
    if (last - first).days >= MAX_DAYS:
        raise v.ValidationError('Der Zeitraum darf höchstens zwei Jahre umfassen.', 'from')
    return reports.Filters(first, last, v.integer(args, 'course_id', 'Kurs', 1, 2**31 - 1),
                           v.integer(args, 'level_id', 'Niveau', 1, 2**31 - 1))


def _respond(kind, body):
    if request.args.get('format') != 'csv':
        return jsonify(body)
    table = next((t for t in body['tables'] if t['id'] == request.args.get('table')), None)
    if table is None:
        raise v.ValidationError('Unbekannte Tabelle für den Export.', 'table')
    period = body['period']
    audit.log(auth.actor(), 'report.export', entity_type='report', entity_name=TITLES[kind],
              summary=f'Bericht exportiert: {TITLES[kind]} – {table["title"]} '
                      f'({de_day(period["from"])} – {de_day(period["to"])}, {len(table["rows"])} Zeilen)',
              detail={'report': kind, 'table': table['id'], 'filters': period})
    db.session.commit()
    name = f'{kind}_{table["id"]}_{period["from"]}_{period["to"]}.csv'
    return Response(csv_export.render(table), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{name}"',
                             'Cache-Control': 'private, no-store'})


@bp.route('/attendance', methods=['GET'])
@auth.require_permission('report.view')
def attendance_report():
    return _respond('attendance', reports.attendance_report(auth.current_identity(), _filters(request.args)))


@bp.route('/academic', methods=['GET'])
@auth.require_permission('report.view')
def academic_report():
    return _respond('academic', reports.academic_report(auth.current_identity(), _filters(request.args)))


@bp.route('/instructors', methods=['GET'])
@auth.require_permission('report.view')
def instructor_report():
    return _respond('instructors', reports.instructor_report(auth.current_identity(), _filters(request.args)))


@bp.route('/candidates/<int:cid>', methods=['GET'])
@auth.require_permission('report.view')
def candidate_report(cid):
    identity = auth.current_identity()
    trainee = db.session.get(Trainee, cid)
    if trainee is None or not scope.can_see_trainee(identity, cid):
        raise v.NotFound('Kandidat nicht gefunden.')
    filters = _filters(request.args)
    if 'from' not in request.args:           # Kandidatenbericht: ohne Angabe der ganze Verlauf
        filters.first = min([d for d in (trainee.start_date, *reports.first_activity(cid)) if d] + [filters.last])
    return jsonify(reports.candidate_report(identity, trainee, filters))


_PERIOD = {'from': '2026-07-01', 'to': '2026-09-28', 'course_id': None, 'level_id': None}
_TABLE = {'id': 'candidates', 'title': 'Anwesenheit je Kandidat',
          'columns': [{'key': 'name', 'label': 'Name', 'type': 'candidate'}, {'key': 'rate', 'label': 'Quote',
                                                                             'type': 'rate'}],
          'rows': [{'candidate_id': 5, 'name': 'Budi Santoso', 'rate': 0.9444}]}
_FILTER = ('Zeitraum from/to (JJJJ-MM-TT, Standard letzte 90 Tage, max. 2 Jahre), course_id, level_id; '
           '?format=csv&table=<id> liefert eine Tabelle als CSV (Semikolon, UTF-8, Export wird protokolliert)')
DOCS = [
    {'path': '/api/reports/attendance', 'method': 'GET',
     'description': 'Anwesenheitsbericht: je Kandidat und je Kurs Anwesend/Verspätet/Entschuldigt/Abwesend, Quote, '
                    'Minuten zu spät — ' + _FILTER + ' — report.view',
     'response_example': {'period': _PERIOD, 'summary': {'candidates': 24, 'with_entries': 20, 'absences': 12, 'late': 8,
                                                         'attendance': {'rate': 0.918}}, 'tables': [_TABLE]}},
    {'path': '/api/reports/academic', 'method': 'GET',
     'description': 'Leistungsbericht: Ø je Bewertungsvorlage + Bestehensquote, Fertigkeiten (Ø/Min/Max), neueste '
                    'Bewertung je Kandidat, Module je Kurs — ' + _FILTER + ' — report.view',
     'response_example': {'period': _PERIOD, 'summary': {'candidates': 24, 'assessments': 40, 'avg_latest': 74.5,
                                                         'pass_rate': 0.85}, 'tables': [_TABLE]}},
    {'path': '/api/reports/instructors', 'method': 'GET',
     'description': 'Dozentenbericht: Kurse, gehaltene/geplante Stunden im Zeitraum, Kandidaten, Bewertungen '
                    'abgeschlossen/offen, offene Anwesenheit — ' + _FILTER + ' — report.view',
     'response_example': {'period': _PERIOD, 'summary': {'instructors': 2, 'hours_held': 48.0, 'assessments_final': 30,
                                                         'assessments_open': 2}, 'tables': [_TABLE]}},
    {'path': '/api/reports/candidates/<id>', 'method': 'GET',
     'description': 'Kandidatenbericht (druckbar): Stammdaten, Niveau, Kurse, abgeschlossene Bewertungen mit '
                    'Kategorien, Feedback, Fertigkeiten, Module, Anwesenheit (Zeitraum + gesamt); ohne interne '
                    'Notizen; ohne from = seit Beginn — report.view',
     'response_example': {'period': _PERIOD, 'candidate': {'id': 5, 'name': 'Budi Santoso', 'courses': []},
                          'assessments': [], 'feedback': [], 'progress': {'skills': [], 'modules': []},
                          'attendance': {'period': None, 'total': {'rate': None}}}},
]

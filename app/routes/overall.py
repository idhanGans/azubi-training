"""Overall rating (Gesamtbewertung): ranking and report per Azubi, each also as Excel/PDF (`?format=xlsx|pdf`).

`rating.view`: the team with `report.view` sees all active candidates, everyone else (SPV/leader) only their
assigned ones (`services/supervision.py`) — also in the downloads. Every download is in the activity log.
Calculation: `services/overall.py`.
"""
from flask import Blueprint, Response, jsonify, request

from app import auth
from app.extensions import db
from app.models.department import Department
from app.models.trainee import Trainee
from app.services import (audit, doc_export, overall, overall_export, overall_months, rating_board, review_notes,
                          supervision, validation as v)
from app.services.local_time import de_day

bp = Blueprint('overall', __name__, url_prefix='/api')

_FORMATS = {'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', doc_export.xlsx),
            'pdf': ('application/pdf', doc_export.pdf)}


def _format():
    value = request.args.get('format')
    if value is not None and value not in _FORMATS:
        raise v.ValidationError('Bitte „xlsx" oder „pdf" als Format angeben.', 'format')
    return value


def _download(fmt, doc, filename, summary, detail):
    audit.log(auth.actor(), 'report.export', entity_type='report', entity_name=doc['title'][:200],
              summary=summary, detail={**detail, 'format': fmt})
    db.session.commit()
    mimetype, render = _FORMATS[fmt]
    return Response(render(doc), mimetype=mimetype,
                    headers={'Content-Disposition': f'attachment; filename="{filename}.{fmt}"',
                             'Cache-Control': 'private, no-store'})


def _period_text(first, last):
    return f'{de_day(first)} – {de_day(last)}' if first else 'gesamter Verlauf'


@bp.route('/overall', methods=['GET'])
@auth.require_permission('rating.view')
def ranking():
    fmt = _format()
    first, last = v.optional_period(request.args, 'gesamter Verlauf')
    department_id = v.integer(request.args, 'department_id', 'Abteilung', 1, 2**31 - 1)
    department = db.session.get(Department, department_id) if department_id else None
    if department_id and department is None:
        raise v.ValidationError('Unbekannte Abteilung.', 'department_id')
    identity = auth.current_identity()
    body = overall.overview(identity, department_id, first, last)
    if fmt is None:
        review_notes.attach(body, identity)
        return jsonify(body)
    doc = overall_export.overview_doc(body, department.name if department else None)
    return _download(fmt, doc, f'gesamtbewertung_{(first or "gesamt")}',
                     f'Gesamtbewertung heruntergeladen ({fmt.upper()}, {_period_text(first, last)}, '
                     f'{len(body["rows"])} Azubis)',
                     {'report': 'overall', 'department_id': department_id, 'period': body['period']})


@bp.route('/overall/<int:tid>', methods=['GET'])
@auth.require_permission('rating.view')
def trainee_report(tid):
    fmt = _format()
    first, last = v.optional_period(request.args, 'gesamter Verlauf')
    identity = auth.current_identity()
    trainee = db.session.get(Trainee, tid)
    if not supervision.can_see(identity, trainee):
        raise v.NotFound('Kandidat nicht gefunden.')
    body = overall.detail(identity, trainee, first, last)
    if fmt is None:
        return jsonify(body)
    return _download(fmt, overall_export.detail_doc(body), f'azubi_{trainee.candidate_no}',
                     f'Azubi-Bericht heruntergeladen: {trainee.name} ({fmt.upper()}, {_period_text(first, last)})',
                     {'report': 'overall_trainee', 'trainee_id': tid, 'period': body['period']})


@bp.route('/overall/months', methods=['GET'])
@auth.require_permission('report.view')
def months_overview():
    """Month comparison of all active Azubis (team with `report.view`)."""
    started = rating_board.months_info()['months']
    first = v.integer(request.args, 'from_month', 'Monat A', 1, rating_board.PROGRAM_MONTHS)
    last = v.integer(request.args, 'to_month', 'Monat B', 1, rating_board.PROGRAM_MONTHS)
    pair = overall_months.default_pair()
    if first is not None or last is not None:
        if first is None or last is None or first >= last:
            raise v.ValidationError('Bitte zwei Monate wählen: den früheren und den späteren.', 'to_month')
        if last not in started:
            raise v.ValidationError(f'Monat {last} hat noch nicht begonnen.', 'to_month')
        pair = (first, last)
    department_id = v.integer(request.args, 'department_id', 'Abteilung', 1, 2**31 - 1)
    supervisor = v.text(request.args, 'supervisor', 'SPV', 120)
    trend = request.args.get('trend') or None
    if trend is not None and trend not in overall_months.TRENDS:
        raise v.ValidationError('Unbekannter Trend.', 'trend')
    return jsonify(overall_months.overview(pair, department_id, supervisor, trend))


@bp.route('/overall/<int:tid>/months', methods=['GET'])
@auth.require_permission('rating.view')
def trainee_months(tid):
    """Month history of one Azubi (same visibility as the Azubi report)."""
    trainee = db.session.get(Trainee, tid)
    if not supervision.can_see(auth.current_identity(), trainee):
        raise v.NotFound('Kandidat nicht gefunden.')
    return jsonify(overall_months.history(trainee))


@bp.route('/overall/notes', methods=['PUT'])
@auth.require_permission('note.edit')
def set_note():
    """Set the review note per Azubi on a fixed 2-week checkpoint (empty text deletes it)."""
    data = request.get_json(silent=True) or {}
    tid = v.integer(data, 'trainee_id', 'Kandidat', 1, 2**31 - 1)
    trainee = db.session.get(Trainee, tid) if tid else None
    if trainee is None or trainee.is_archived:
        raise v.ValidationError('Bitte einen aktiven Kandidaten auswählen.', 'trainee_id')
    checkpoint = v.iso_date(data, 'checkpoint', 'Stichtag')
    if checkpoint not in review_notes.checkpoints_iso():
        raise v.ValidationError('Unbekannter Stichtag.', 'checkpoint')
    text = v.text(data, 'text', 'Notiz', review_notes.MAX_CHARS) or ''
    note = review_notes.set_note(trainee.id, checkpoint, text, auth.actor())
    audit.log(auth.actor(), 'note.edit', entity_type='trainee', entity_id=trainee.id, entity_name=trainee.name,
              summary=f'Review-Notiz {de_day(checkpoint)} für {trainee.name} '
                      f'{"gespeichert" if note["text"] else "gelöscht"}',
              detail={'checkpoint': checkpoint})
    db.session.commit()
    return jsonify(note)


_PART = {'score': 82.5}
_ROW = {'id': 5, 'candidate_no': 'K-00005', 'name': 'Raka Bayu', 'nickname': None,
        'abteilung': 'Erkelenz – PV-Assistent', 'department': {'id': 3, 'name': 'Erkelenz'},
        'supervisor': 'citra_lestari', 'leaders': ['galih_santoso'],
        'parts': {'report': {'score': 91.0, 'workdays': 15, 'days_reported': 14, 'hours': 88.0, 'target_hours': 90,
                             'hours_percent': 97.8, 'regularity_percent': 93.3, 'detail_percent': 80.0,
                             'from': '2026-09-17', 'to': '2026-10-08'},
                  'german': {'score': 96.3, 'count': 4, 'average_total': 19.5, 'lessons_percent': 97.5,
                             'latest_level': 'A', 'attendance': {'present': 4, 'late': 0, 'excused': 0, 'absent': 0,
                                                                 'rate': 1.0}},
                  'spv': {'score': 80.0, 'count': 2, 'mean': 8.0, 'r_practical': 8.0, 'r_reliability': 8.5,
                          'r_motivation': 7.5},
                  'intern': {'score': None, 'count': 0}},
        'total': 89.5, 'missing': ['intern'], 'rank': 1, 'department_rank': 1}
_RULES = {'parts': list(overall.WEIGHTS), 'weights': overall.WEIGHTS, 'score_max': 100, 'hours_per_workday': 6, 'day_hours_cap': 8,
          'detail_full_chars': 400, 'report_parts': overall.REPORT_PARTS, 'german_parts': overall.GERMAN_PARTS,
          'german_max': 20, 'rating_scale': [1, 10], 'categories': ['r_practical', 'r_reliability', 'r_motivation']}
DOCS = [
    {'path': '/api/overall', 'method': 'GET',
     'description': 'Gesamtbewertung: Report 10 % + Deutsch 40 % + SPV 30 % + Intern 20 % (je 0–100, fehlender Teil '
                    '= „Ausstehend"; Gesamt aus den vorhandenen Teilen gewichtet, Rang schon vor der vollstaendigen '
                    'Bewertung), Rang gesamt (nur mit report.view) und je Abteilung. Filter '
                    '?department_id=, ?from=&to= (beide oder keins = gesamter Verlauf, max. 2 Jahre); '
                    '?format=xlsx|pdf = Download (im Verlauf) — rating.view; ohne report.view nur die als SPV/Leiter '
                    'zugeordneten Kandidaten',
     'response_example': {'rules': _RULES, 'period': {'from': None, 'to': None}, 'department_id': None,
                          'departments': [{'id': 3, 'name': 'Erkelenz'}], 'overall_rank': True,
                          'note_checkpoints': ['2026-10-19', '2026-11-02'], 'can_edit_notes': True,
                          'rows': [{**_ROW, 'notes': {'2026-10-19': 'Sehr engagiert.'}}]}},
    {'path': '/api/overall/<trainee_id>', 'method': 'GET',
     'description': 'Bericht je Azubi: alle Teile mit Herleitung, Gesamt, Rang, Gruppen und Bewertungen (fremde '
                    'Bewerter + Notizen nur mit assessment.view, sonst nur die eigenen); gleiche Filter und '
                    '?format=xlsx|pdf — rating.view; 404 fuer nicht zugeordnete/archivierte Kandidaten',
     'response_example': {**_ROW, 'rules': _RULES, 'period': {'from': None, 'to': None},
                          'groups': ['Deutschkurs Gruppe 3'], 'all_ratings': True, 'overall_rank': True,
                          'ratings': [{'id': 7, 'kind': 'SPV', 'rater': 'citra_lestari', 'r_practical': 8,
                                       'r_reliability': 9, 'r_motivation': 7, 'note': '…',
                                       'created_at': '2026-10-08T03:00:00+00:00'}]}},
    {'path': '/api/overall/months', 'method': 'GET',
     'description': 'Monatsvergleich aller aktiven Azubis — report.view. Je begonnenem Programm-Monat Gesamt und '
                    'Teile (Report/Deutsch nach den Tagen des Monats, laufender Monat bis gestern; SPV/Intern nach '
                    'dem Bewertungs-Monat), Vergleich Monat A -> B (?from_month=&to_month=, ohne = die zwei '
                    'letzten abgeschlossenen Monate, sonst 1 -> 2) ueber die in BEIDEN Monaten vorhandenen Teile: '
                    'Aenderung in Punkten und %, Trend IMPROVED/STAGNANT/DECLINED (Band `rules.trend_band`) oder '
                    'OPEN (nicht vergleichbar); Gesamt + Rang ueber das ganze Programm. Filter ?department_id=, '
                    '?supervisor=, ?trend= gelten auch fuer `summary` (Anzahl je Trend, Kohorten-Durchschnitt, '
                    'Top-Verbesserer, groesste Rueckgaenge)',
     'response_example': {'rules': {'trend_band': 2.0, 'trends': ['IMPROVED', 'STAGNANT', 'DECLINED', 'OPEN'],
                                    'weights': overall.WEIGHTS, 'parts': list(overall.WEIGHTS)},
                          'month': 2, 'started': [1, 2], 'pair': [1, 2], 'pairs': [[1, 2]], 'default_pair': [1, 2],
                          'calendar': [{'month': 1, 'from': '2026-09-17', 'to': '2026-10-16', 'started': True}],
                          'departments': [{'id': 3, 'name': 'Erkelenz'}], 'supervisors': ['citra_lestari'],
                          'summary': {'counts': {'IMPROVED': 1, 'STAGNANT': 0, 'DECLINED': 0, 'OPEN': 0},
                                      'comparable': 1, 'cohort': {'from': 70.0, 'to': 75.2, 'delta': 5.2},
                                      'month_average': {'1': 70.0, '2': 75.2},
                                      'top_improvers': [{'id': 5, 'name': 'Raka Bayu', 'from': 70.0, 'to': 75.2,
                                                         'delta': 5.2}], 'top_decliners': []},
                          'rows': [{'id': 5, 'candidate_no': 'K-00005', 'name': 'Raka Bayu', 'total': 89.5,
                                    'rank': 1, 'supervisor': 'citra_lestari', 'department': {'id': 3, 'name': 'Erkelenz'},
                                    'months': {'1': {'total': 70.0, 'running': False, 'missing': [],
                                                     'parts': {'report': 80.0, 'german': 65.0, 'spv': 70.0,
                                                               'intern': 70.0}}},
                                    'compare': {'trend': 'IMPROVED', 'parts': ['report', 'german', 'spv', 'intern'],
                                                'from': 70.0, 'to': 75.2, 'delta': 5.2, 'percent': 7.4}}]}},
    {'path': '/api/overall/<trainee_id>/months', 'method': 'GET',
     'description': 'Monatsverlauf eines Azubis: je begonnenem Monat Gesamt und Teile mit Herleitung (wie '
                    '/api/overall/<id>), Aenderung zwischen aufeinanderfolgenden Monaten (`steps`, gleiche Regel wie '
                    'der Monatsvergleich) und die neueste vergleichbare (`latest`) — rating.view, gleiche '
                    'Sichtbarkeit wie der Azubi-Bericht (404 sonst)',
     'response_example': {'month': 2, 'calendar': [{'month': 1, 'from': '2026-09-17', 'to': '2026-10-16',
                                                    'started': True}],
                          'history': [{'month': 1, 'running': False, 'total': 70.0, 'missing': [],
                                       'parts': {'spv': _PART}}],
                          'steps': [{'from_month': 1, 'to_month': 2, 'trend': 'IMPROVED', 'delta': 5.2,
                                     'percent': 7.4, 'from': 70.0, 'to': 75.2, 'parts': ['spv']}],
                          'latest': {'from_month': 1, 'to_month': 2, 'trend': 'IMPROVED', 'delta': 5.2}}},
    {'path': '/api/overall/notes', 'method': 'PUT',
     'description': 'Review-Notiz je Azubi an einem festen 2-Wochen-Stichtag setzen (leerer Text loescht sie) '
                    '— note.edit (nur Super-Admin). Body: trainee_id, checkpoint (YYYY-MM-DD aus note_checkpoints), '
                    'text (bis 2000 Zeichen)',
     'request_example': {'trainee_id': 5, 'checkpoint': '2026-10-19', 'text': 'Sehr engagiert.'},
     'response_example': {'trainee_id': 5, 'checkpoint': '2026-10-19', 'text': 'Sehr engagiert.',
                          'updated_by': 'root_admin', 'updated_at': '2026-10-19T09:00:00+00:00'}},
]

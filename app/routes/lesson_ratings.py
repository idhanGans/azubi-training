"""Module rating (Modul-Bewertung) per session (Termin) (Panduan Penilaian Deutschkurs): record, live preview,
evaluation per group, own feedback for candidates. Business logic in services/lesson_ratings.py, computation
in lesson_scoring.py.

Reading `assessment.view`, recording `assessment.create` (instructors: only sessions of their courses, `scope`).
"""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.course import Course
from app.models.course_session import CourseSession
from app.services import attendance, audit, lesson_ratings as svc, lesson_scoring, notifications, scope
from app.services import validation as v
from app.services.local_time import de_day

bp = Blueprint('lesson_ratings', __name__, url_prefix='/api')


def _session(sid):
    session = db.session.get(CourseSession, sid)
    if session is None or not scope.can_see_course(auth.current_identity(), session.course):
        raise v.NotFound('Termin nicht gefunden.')
    return session


@bp.route('/sessions/<int:sid>/lesson-ratings', methods=['GET'])
@auth.require_permission('assessment.view')
def get_sheet(sid):
    session = _session(sid)
    module, unit = svc.pick_sheet(session, request.args)
    return jsonify(svc.sheet(session, module, unit))


@bp.route('/sessions/<int:sid>/lesson-ratings', methods=['PUT'])
@auth.require_permission('assessment.create')
def record(sid):
    session = _session(sid)
    data = request.get_json(silent=True) or {}
    attendance.lock(session)
    attendance.check_recordable(session)
    module, unit = svc.pick_sheet(session, data)
    att_changes, changes = svc.record(session, module, unit, data, auth.actor())
    if session.status == 'SCHEDULED':
        session.status = 'COMPLETED'                                     # recorded = held
    if att_changes or changes:
        day = svc.session_dict(session, {})['date']
        audit.log(auth.actor(), 'lesson_rating.record', entity_type='course', entity_id=session.course_id,
                  entity_name=session.course.name,
                  summary=f'Modul-Bewertung: {session.course.name}, {module.name} (Einheit {unit}), {de_day(day)}',
                  detail={'session_id': session.id, 'module_id': module.id, 'unit': unit, 'changes': changes,
                          'attendance': att_changes})
    notifications.resolve(key=f'attendance:{session.id}')                 # whole group recorded
    db.session.commit()
    return jsonify(svc.sheet(session, module, unit))


@bp.route('/sessions/<int:sid>/lesson-ratings/move', methods=['POST'])
@auth.require_permission('assessment.create')
def move(sid):
    """Reassign a sheet filed under the wrong module/unit — stars, notes and attendance stay."""
    session = _session(sid)
    data = request.get_json(silent=True) or {}
    attendance.lock(session)
    attendance.check_recordable(session)
    module, unit = svc.pick_sheet(session, data)
    target, target_unit, count = svc.move_sheet(session, module, unit, data)
    day = svc.session_dict(session, {})['date']
    audit.log(auth.actor(), 'lesson_rating.move', entity_type='course', entity_id=session.course_id,
              entity_name=session.course.name,
              summary=f'Modul-Bewertung umgehängt: {session.course.name}, {de_day(day)}, {module.name} (Einheit {unit}) '
                      f'-> {target.name} (Einheit {target_unit})',
              detail={'session_id': session.id, 'count': count, 'from': {'module_id': module.id, 'unit': unit},
                      'to': {'module_id': target.id, 'unit': target_unit}})
    db.session.commit()
    return jsonify(svc.sheet(session, target, target_unit))


@bp.route('/lesson-ratings/evaluate', methods=['POST'])
@auth.require_permission('assessment.create')
def evaluate():
    """Live preview: points + level from the stars — computed only on the server."""
    return jsonify({'results': svc.preview(request.get_json(silent=True) or {})})


@bp.route('/courses/<int:cid>/lesson-report', methods=['GET'])
@auth.require_permission('assessment.view')
def course_report(cid):
    course = db.session.get(Course, cid)
    if course is None or not scope.can_see_course(auth.current_identity(), course):
        raise v.NotFound('Kurs nicht gefunden.')
    first, last = v.optional_period(request.args, 'ganzer Kurs')
    return jsonify(svc.report(course, first, last))


@bp.route('/my-lesson-ratings', methods=['GET'])
@auth.candidate_only
def my_lesson_ratings():
    """Candidate: own module ratings (stars, points, level, strength, target) — without internal note."""
    return jsonify({'ratings': svc.history(auth.current_identity().trainee_id, public=True),
                    'rules': lesson_scoring.rules()})


_RULES = {'aspects': ['v', 'r', 'w', 'f', 'p'], 'aspect_min': 1, 'aspect_max': 3,
          'behavior_max': {'pu': 1, 'mi': 2, 'ha': 2}, 'ha_without_homework': 2,
          'feedback_codes': ['V', 'R', 'W', 'F', 'P', 'L'],
          'levels': [{'code': 'A', 'min': 18, 'max': 20}, {'code': 'B', 'min': 15, 'max': 17},
                     {'code': 'C', 'min': 12, 'max': 14}, {'code': 'D', 'min': 5, 'max': 11}],
          'capped_level': 'C', 'coaching_level': 'D', 'challenge_level': 'A', 'total_min': 5, 'total_max': 20}
_RESULT = {'part_a': 13, 'part_b': 5, 'total': 18, 'level': 'C', 'capped': True, 'complete': True}
_ENTRY = {'trainee_id': 5, 'attendance': 'PRESENT', 'v': 3, 'r': 3, 'w': 3, 'f': 3, 'p': 1, 'pu': 1, 'mi': 2,
          'ha': 2, 'strength': ['W', 'L'], 'target': ['P'], 'note': 'Fragt nicht nach'}
_SHEET = {'module': {'id': 3, 'name': 'Modul 3 – Kommunikation im Betrieb'}, 'unit': 1}

DOCS = [
    {'path': '/api/sessions/<id>/lesson-ratings', 'method': 'GET',
     'description': 'Modul-Bewertung eines Termins für EIN Blatt (Modul + Einheit; ein Termin kann mehrere Module '
                    'abdecken): ?module_id=&unit= (ohne: erstes bewertetes Blatt bzw. Modul des Termins mit geplanter '
                    'Einheit; Modul muss zum Curriculum gehören, sonst 400). Termin, Blatt, schon bewertete Blätter '
                    '(`sheets`), wählbare Module, Kursteilnehmer mit Anwesenheit und Bewertung (Sterne V R W F P 1–3, '
                    'Pü 0–1, Mi 0–2, HA 0–2 oder leer = keine Hausaufgabe — leere Werte erlaubt, dann ohne Gesamt; '
                    'Stärke/Ziel als Liste von Codes, interne Notiz, Ergebnis), Regel-Zahlen (`rules`) — '
                    'assessment.view; Dozenten: nur eigene Kurse',
     'response_example': {'session': {'id': 7, 'date': '2026-10-05', 'unit': 1, 'module': {'id': 3, 'name': 'Modul 3'}},
                          'sheet': _SHEET, 'sheets': [{**_SHEET, 'rated': 5}],
                          'modules': [{'id': 3, 'name': 'Modul 3 – Kommunikation im Betrieb'}], 'unit_max': 99,
                          'entries': [{'trainee': {'id': 5, 'name': 'Budi'}, 'attendance': {'status': 'PRESENT'},
                                       'rating': {**_ENTRY, **_SHEET, 'result': _RESULT}}],
                          'homework_none': False, 'rules': _RULES,
                          'summary': {'expected': 6, 'attended': 5, 'rated': 5}}},
    {'path': '/api/sessions/<id>/lesson-ratings', 'method': 'PUT',
     'description': 'Ganze Gruppe für EIN Blatt speichern (module_id + unit wie beim GET; alle aktuellen Teilnehmer, '
                    'frühere nach Gruppenwechsel freiwillig): '
                    'Anwesenheit PRESENT|LATE|EXCUSED|ABSENT gilt für den ganzen Termin; für Anwesende Sterne, Pü, Mi, '
                    'Stärke/Ziel (Code oder Liste V R W F P L) — leere Felder erlaubt, ganz ohne Werte = anwesend ohne '
                    'Bewertung; HA Pflicht, wenn nicht homework_none und etwas bewertet wird. Fehlende ohne Sterne '
                    '(Notiz = Grund des Fehlens an der Anwesenheit; ihre Sterne in ALLEN Blättern des Termins fallen '
                    'weg). Ab 15 Min. vor Beginn, nicht bei abgesagten Terminen (409); setzt den Termin auf COMPLETED; '
                    'Verlauf lesson_rating.record — assessment.create',
     'request_example': {'module_id': 3, 'unit': 1, 'homework_none': False,
                         'entries': [_ENTRY, {'trainee_id': 6, 'attendance': 'ABSENT', 'note': 'krank'}]},
     'response_example': {'summary': {'expected': 2, 'attended': 1, 'rated': 1}}},
    {'path': '/api/sessions/<id>/lesson-ratings/move', 'method': 'POST',
     'description': 'Blatt umhängen (falsches Modul/falsche Einheit gewählt): alle Bewertungen von module_id + unit '
                    'nach to_module_id + to_unit (ohne to_unit: vorgeschlagene Einheit), Modul aus demselben Curriculum '
                    '(sonst 400). 409, wenn das Blatt leer ist oder das Ziel an diesem Termin schon Bewertungen hat. '
                    'Antwort = Ziel-Blatt wie beim GET; Verlauf lesson_rating.move — assessment.create',
     'request_example': {'module_id': 3, 'unit': 1, 'to_module_id': 10, 'to_unit': 1},
     'response_example': {'sheet': {'module': {'id': 10, 'name': 'Modul 10'}, 'unit': 1},
                          'summary': {'expected': 6, 'attended': 5, 'rated': 5}}},
    {'path': '/api/lesson-ratings/evaluate', 'method': 'POST',
     'description': 'Live-Vorschau: Punkte (Teil A 5–15, Teil B 0–5, Gesamt 5–20) und Level A–D je Eintrag; '
                    'A/B nur ohne 1-Stern-Aspekt (sonst höchstens C); mit Lücken complete=false und Punkte null, '
                    'leere/ungültige Einträge -> null — assessment.create',
     'request_example': {'homework_none': False, 'entries': [_ENTRY]},
     'response_example': {'results': {'5': _RESULT}}},
    {'path': '/api/courses/<id>/lesson-report', 'method': 'GET',
     'description': 'Auswertung einer Gruppe, optional ?from=&to= (sonst ganzer Kurs, max. 2 Jahre): je Teilnehmer '
                    'Anzahl, Durchschnitt (gesamt nur über Bewertungen mit Gesamt; je Aspekt/Lernverhalten über gefüllte '
                    'Werte), Level-Verteilung, neueste Bewertung mit Gesamt, Trend zum gleich langen Zeitraum davor; '
                    'Gruppe mit schwächstem Aspekt; Verlauf je Termin und Modul/Einheit; Begleitung (Level D) und '
                    'Zusatzaufgaben (Level A) nach neuester Bewertung — assessment.view; Dozenten: nur eigene Kurse',
     'response_example': {'course': {'id': 2, 'name': 'Deutschkurs Gruppe 2'},
                          'period': {'from': '2026-10-01', 'to': '2026-10-31'}, 'rules': _RULES,
                          'group': {'count': 40, 'average': {'total': 15.2}, 'levels': {'A': 5, 'B': 20},
                                    'weakest': ['p']},
                          'participants': [{'trainee': {'id': 5, 'name': 'Budi'}, 'count': 6, 'trend': 1.5,
                                            'latest': {'level': 'C', 'strength': ['W'], 'target': ['P']}}],
                          'sessions': [{'id': 7, 'date': '2026-10-05', **_SHEET, 'rated': 8, 'average_total': 15.4}],
                          'coaching': [{'id': 9, 'name': 'Sari'}], 'challenge': []}},
    {'path': '/api/my-lesson-ratings', 'method': 'GET',
     'description': 'Kandidat: eigene Modul-Bewertungen, neueste zuerst — Sterne, Punkte, Level, Stärke, Ziel, Termin; '
                    'ohne interne Notiz und ohne Team-Logins',
     'response_example': {'ratings': [{'v': 3, 'r': 2, 'strength': ['W'], 'target': ['P'], 'result': _RESULT, **_SHEET,
                                       'session': {'date': '2026-10-05', 'module': {'name': 'Modul 3'}}}],
                          'rules': _RULES}},
]

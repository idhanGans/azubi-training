"""Anwesenheit: je Termin erfassen/korrigieren, Kandidaten sehen ihre eigene.

Dozenten erfassen nur fuer Termine ihrer Kurse (`scope`), Kandidaten sehen
nur sich selbst — ohne interne Notizen.
"""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.course_session import CourseSession
from app.services import attendance as svc, audit, lesson_ratings, notifications, scope, validation as v
from app.services.local_time import de_day

bp = Blueprint('attendance', __name__, url_prefix='/api')


def _session(sid):
    session = db.session.get(CourseSession, sid)
    if session is None or not scope.can_see_course(auth.current_identity(), session.course):
        raise v.NotFound('Termin nicht gefunden.')
    return session


def _body(session):
    entries = svc.sheet(session)
    records = [e['attendance'] for e in entries if e['attendance']]
    present = sum(1 for r in records if r['status'] in svc.ATTENDED)
    counted = sum(1 for r in records if r['status'] in svc.COUNTED)
    return {'session': session.to_dict(), 'entries': entries,
            'summary': {'recorded': len(records), 'expected': sum(1 for e in entries if e['trainee']['in_course']),
                        'rate': svc.rate(present, counted)}}


@bp.route('/sessions/<int:sid>/attendance', methods=['GET'])
@auth.require_permission('attendance.view')
def get_attendance(sid):
    return jsonify(_body(_session(sid)))


@bp.route('/sessions/<int:sid>/attendance', methods=['PUT'])
@auth.require_permission('attendance.manage')
def record_attendance(sid):
    session = _session(sid)
    svc.lock(session)
    svc.check_recordable(session)
    changes = svc.record(session, (request.get_json(silent=True) or {}).get('entries'), auth.actor())
    dropped = lesson_ratings.drop_unattended(session)          # wer jetzt fehlt, hat keine Modul-Bewertung mehr
    if session.status == 'SCHEDULED':
        session.status, session.updated_by = 'COMPLETED', auth.actor()   # erfasst = durchgefuehrt
    if changes:
        day = session.to_dict()['date']
        detail = {'session_id': session.id, 'changes': changes}
        if dropped:
            detail['lesson_ratings_removed'] = dropped
        audit.log(auth.actor(), 'attendance.record', entity_type='course', entity_id=session.course_id,
                  entity_name=session.course.name, summary=f'Anwesenheit erfasst: {session.course.name}, '
                  f'{de_day(day)}', detail=detail)
    body = _body(session)
    if body['summary']['recorded'] >= body['summary']['expected']:
        notifications.resolve(key=f'attendance:{session.id}')      # Hinweis „Anwesenheit offen" erledigt
    db.session.commit()
    return jsonify(body)


@bp.route('/my-attendance', methods=['GET'])
@auth.candidate_only
def my_attendance():
    """Kandidat: eigene Quote + Eintraege (ohne interne Notiz, ohne Erfasser)."""
    tid = auth.current_identity().trainee_id
    rows = svc.recent(tid, limit=200)
    return jsonify({
        'stats': svc.stats_for(tid),
        'records': [{'status': a.status, 'minutes_late': a.minutes_late, 'session': s.public_dict()}
                    for a, s in rows],
    })


_ENTRY = {'trainee': {'id': 5, 'candidate_no': 'K-00005', 'name': 'Budi Santoso', 'nickname': 'Budi',
                      'archived': False, 'in_course': True},
          'attendance': {'id': 1, 'session_id': 7, 'trainee_id': 5, 'status': 'LATE', 'minutes_late': 10,
                         'note': 'Bus verspätet', 'recorded_by': 'maria_weber'}}
_STATS = {'present': 15, 'late': 2, 'excused': 1, 'absent': 1, 'recorded': 19, 'rate': 0.9444}

DOCS = [
    {'path': '/api/sessions/<id>/attendance', 'method': 'GET',
     'description': 'Erfassungsliste eines Termins: Kursteilnehmer mit Eintrag (oder null) + Zusammenfassung — '
                    'attendance.view; Dozenten: nur eigene Kurse',
     'response_example': {'session': {'id': 7, 'date': '2026-09-25', 'start': '10:00', 'end': '12:00'},
                          'entries': [_ENTRY], 'summary': {'recorded': 1, 'expected': 12, 'rate': 1.0}}},
    {'path': '/api/sessions/<id>/attendance', 'method': 'PUT',
     'description': 'Anwesenheit erfassen/korrigieren (Status PRESENT|LATE|EXCUSED|ABSENT, minutes_late nur bei '
                    'LATE, interne Notiz) für aktuelle und frühere Kursteilnehmer (Gruppenwechsel); je Termin + Kandidat genau '
                    'ein Eintrag; frühestens 15 Min. vor Beginn, '
                    'nicht bei abgesagten Terminen (409); setzt den Termin auf COMPLETED — attendance.manage',
     'request_example': {'entries': [{'trainee_id': 5, 'status': 'LATE', 'minutes_late': 10, 'note': 'Bus verspätet'},
                                     {'trainee_id': 6, 'status': 'PRESENT'}]},
     'response_example': {'session': {'id': 7, 'status': 'COMPLETED'}, 'entries': [_ENTRY],
                          'summary': {'recorded': 2, 'expected': 12, 'rate': 1.0}}},
    {'path': '/api/my-attendance', 'method': 'GET',
     'description': 'Kandidat: eigene Anwesenheitsquote + Einträge (ohne interne Notiz). Quote = (Anwesend + '
                    'Verspätet) / (Anwesend + Verspätet + Abwesend); Entschuldigt zählt nicht',
     'response_example': {'stats': _STATS, 'records': [{'status': 'PRESENT', 'minutes_late': None,
                                                        'session': {'id': 7, 'date': '2026-09-25'}}]}},
]

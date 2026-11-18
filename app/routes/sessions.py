"""Schedule (Stundenplan): create, move, cancel sessions, assign instructor/module, calendar queries.

Instructors without `candidate.view_all` see only sessions of their courses
(`app/services/scope.py`); candidates see only their own schedule.
"""
from datetime import timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import auth
from app.extensions import db
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.instructor import Instructor
from app.services import audit, notifications, scheduling, scope, validation as v
from app.services.local_time import day_range_utc, de_day, today

bp = Blueprint('sessions', __name__, url_prefix='/api')

MAX_RANGE_DAYS = 62
_NOT_AUDITED = ('updated_at', 'updated_by', 'module_id', 'instructor_id', 'course_id', 'starts_at', 'ends_at',
                'duration_minutes', 'course', 'created_at', 'created_by')


def _get(sid):
    session = db.session.get(CourseSession, sid)
    if session is None or not scope.can_see_course(auth.current_identity(), session.course):
        raise v.NotFound('Termin nicht gefunden.')
    return session


def _audit_view(session):
    data = session.to_dict()
    view = {k: val for k, val in data.items() if k not in _NOT_AUDITED}
    view['module'] = data['module']['name'] if data['module'] else None
    view['instructor'] = data['instructor']['name'] if data['instructor'] else None
    return view


def _range(args):
    first = v.day(args, 'from', 'Von')
    last = v.day(args, 'to', 'Bis')
    if first is None or last is None:
        raise v.ValidationError('Bitte einen Zeitraum (from, to) angeben.', 'from')
    if last < first or (last - first).days > MAX_RANGE_DAYS:
        raise v.ValidationError(f'Der Zeitraum muss zwischen 1 und {MAX_RANGE_DAYS + 1} Tagen liegen.', 'to')
    return day_range_utc(first, last)


def _ids(args, *names):
    return {name: v.integer(args, name, 'Filter', 1, 2**31 - 1) for name in names}


def _with_counts(sessions):
    counts = dict(db.session.query(CourseParticipant.course_id, func.count(CourseParticipant.trainee_id))
                  .filter(CourseParticipant.course_id.in_({s.course_id for s in sessions}))
                  .group_by(CourseParticipant.course_id).all()) if sessions else {}
    return [{**s.to_dict(), 'participant_count': counts.get(s.course_id, 0)} for s in sessions]


@bp.route('/sessions', methods=['GET'])
@auth.require_permission('schedule.view')
def list_sessions():
    starts, ends = _range(request.args)
    f = _ids(request.args, 'course_id', 'instructor_id', 'trainee_id', 'level_id', 'module_id')
    q = (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
         .filter(CourseSession.starts_at < ends, CourseSession.ends_at > starts))
    condition = scope.course_condition(auth.current_identity())
    q = q.filter(condition) if condition is not None else q
    if not f['course_id']:
        q = q.filter(Course.archived_at.is_(None))
    if request.args.get('include_cancelled') != '1':
        q = q.filter(CourseSession.status != 'CANCELLED')
    for name, column in (('course_id', CourseSession.course_id), ('instructor_id', CourseSession.instructor_id),
                         ('level_id', Course.level_id), ('module_id', CourseSession.module_id)):
        if f[name]:
            q = q.filter(column == f[name])
    if f['trainee_id']:
        q = q.filter(CourseSession.course_id.in_(
            db.select(CourseParticipant.course_id).where(CourseParticipant.trainee_id == f['trainee_id'])))
    return jsonify({'sessions': _with_counts(q.order_by(CourseSession.starts_at).all())})


@bp.route('/sessions/<int:sid>', methods=['GET'])
@auth.require_permission('schedule.view')
def get_session(sid):
    return jsonify({'session': _with_counts([_get(sid)])[0]})


@bp.route('/sessions', methods=['POST'])
@auth.require_permission('schedule.create')
def create_sessions():
    data = request.get_json(silent=True) or {}
    course = db.session.get(Course, data.get('course_id')) if isinstance(data.get('course_id'), int) else None
    if course is None:
        raise v.ValidationError('Bitte einen Kurs auswählen.', 'course_id')
    scheduling.lock()
    rows = scheduling.read_new(data, course)
    windows = [(r['starts_at'], r['ends_at']) for r in rows]
    scheduling.check_conflicts(windows, rows[0]['instructor_id'], scheduling.participant_ids(course.id))
    sessions = [CourseSession(**r, created_by=auth.actor()) for r in rows]
    db.session.add_all(sessions)
    db.session.flush()
    first, last = sessions[0].to_dict(), sessions[-1].to_dict()
    summary = (f'Termin angelegt: {course.name}, {de_day(first["date"])}, {first["start"]}–{first["end"]} Uhr'
               if len(sessions) == 1 else
               f'{len(sessions)} Termine angelegt: {course.name} (wöchentlich, '
               f'{de_day(first["date"])} – {de_day(last["date"])})')
    audit.log(auth.actor(), 'session.create', entity_type='course', entity_id=course.id, entity_name=course.name,
              summary=summary, detail={'session_ids': [s.id for s in sessions]})
    instructor = db.session.get(Instructor, sessions[0].instructor_id) if sessions[0].instructor_id else None
    warnings = scheduling.availability_warnings(instructor, windows)
    db.session.commit()
    return jsonify({'sessions': [s.to_dict() for s in sessions], 'warnings': warnings}), 201


@bp.route('/sessions/<int:sid>', methods=['PATCH'])
@auth.require_permission('schedule.edit')
def update_session(sid):
    session = _get(sid)
    scheduling.lock()
    before = _audit_view(session)
    values = scheduling.read_changes(request.get_json(silent=True) or {}, session)
    for key, value in values.items():
        setattr(session, key, value)
    db.session.flush()
    db.session.expire(session)
    active = session.status != 'CANCELLED'
    timing = {'starts_at', 'ends_at', 'instructor_id', 'status'} & set(values)
    if active and timing:
        scheduling.check_conflicts([(session.starts_at, session.ends_at)], session.instructor_id,
                                   scheduling.participant_ids(session.course_id), exclude_ids=[session.id])
    changes = audit.diff(before, _audit_view(session))
    warnings = []
    if changes:
        session.updated_by = auth.actor()
        action = 'session.cancel' if changes.get('status', [None, None])[1] == 'CANCELLED' else 'session.update'
        summary = {'session.cancel': 'Termin abgesagt', 'session.update': 'Termin geändert'}[action]
        if {'date', 'start', 'end'} & set(changes) and action == 'session.update':
            summary = 'Termin verschoben'
        audit.log(auth.actor(), action, entity_type='course', entity_id=session.course_id,
                  entity_name=session.course.name, summary=f'{summary}: {session.course.name}',
                  detail={'session_id': session.id, 'changes': changes})
        if active and timing:
            warnings = scheduling.availability_warnings(session.instructor, [(session.starts_at, session.ends_at)])
        notifications.session_changed(session, changes)
    db.session.commit()
    return jsonify({'session': session.to_dict(), 'warnings': warnings})


@bp.route('/my-schedule', methods=['GET'])
@auth.candidate_only
def my_schedule():
    """Candidate: own sessions (courses in which they are a participant) — without internal notes."""
    args = request.args
    if 'from' in args or 'to' in args:
        starts, ends = _range(args)
    else:
        starts, ends = day_range_utc(today(), today() + timedelta(days=27))
    own = db.select(CourseParticipant.course_id).where(
        CourseParticipant.trainee_id == auth.current_identity().trainee_id)
    sessions = (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
                .filter(CourseSession.course_id.in_(own), Course.archived_at.is_(None),
                        CourseSession.starts_at < ends, CourseSession.ends_at > starts)
                .order_by(CourseSession.starts_at).all())
    return jsonify({'sessions': [s.public_dict() for s in sessions]})

"""Courses (Kurse, classes): list, create/edit, assign instructor + participants.

Instructors without `candidate.view_all` see only their own courses
(`app/services/scope.py`) — other courses respond with 404.
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import auth
from app.extensions import db
from app.models.common import iso, utcnow
from app.models.course import STATUSES, Course
from app.models.course_participant import CourseParticipant
from app.models.trainee import Trainee
from app.services import attendance, audit, courses as svc, notifications, scheduling, scope, validation as v

bp = Blueprint('courses', __name__, url_prefix='/api/courses')

_NOT_AUDITED = ('updated_at', 'updated_by', 'level_id', 'module_id', 'instructor_id')


def _get(cid):
    course = db.session.get(Course, cid)
    if course is None or not scope.can_see_course(auth.current_identity(), course):
        raise v.NotFound('Kurs nicht gefunden.')
    return course


def _audit_view(course):
    """For the activity log: level/module/instructor with NAMES instead of IDs."""
    data = course.to_dict()
    view = {k: val for k, val in data.items() if k not in _NOT_AUDITED}
    for key in ('level', 'module', 'instructor'):
        view[key] = data[key]['name'] if data[key] else None
    return view


def _participant(trainee, added_at):
    return {'id': trainee.id, 'candidate_no': trainee.candidate_no, 'name': trainee.name,
            'nickname': trainee.nickname, 'archived': trainee.is_archived,
            'current_level': trainee.current_level.ref() if trainee.current_level else None,
            'status': trainee.status.ref() if trainee.status else None, 'added_at': iso(added_at)}


@bp.route('', methods=['GET'])
@auth.require_permission('schedule.view')
def list_courses():
    q = Course.query
    condition = scope.course_condition(auth.current_identity())
    if condition is not None:
        q = q.filter(condition)
    q = q.filter(Course.archived_at.isnot(None) if request.args.get('archived') == '1'
                 else Course.archived_at.is_(None))
    for name, column in (('level_id', Course.level_id), ('instructor_id', Course.instructor_id)):
        value = v.integer(request.args, name, 'Filter', 1, 2**31 - 1)
        if value:
            q = q.filter(column == value)
    status = request.args.get('status')
    if status:
        if status not in STATUSES:
            raise v.ValidationError('Unbekannter Status.', 'status')
        q = q.filter(Course.status == status)
    courses = q.order_by(func.lower(Course.name)).all()
    counts = svc.participant_counts([c.id for c in courses])
    return jsonify({'courses': [{**c.to_dict(), 'participant_count': counts.get(c.id, 0)} for c in courses]})


@bp.route('/<int:cid>', methods=['GET'])
@auth.require_permission('schedule.view')
def get_course(cid):
    course = _get(cid)
    rows = svc.participants(cid)
    rates = attendance.stats([t.id for t, _ in rows], Course.id == cid)
    return jsonify({'course': course.to_dict(),
                    'participants': [{**_participant(t, at), 'attendance': rates.get(t.id)} for t, at in rows]})


@bp.route('', methods=['POST'])
@auth.require_permission('schedule.create')
def create_course():
    course = Course(**svc.read(request.get_json(silent=True) or {}), created_by=auth.actor())
    db.session.add(course)
    db.session.flush()
    db.session.refresh(course)
    audit.log(auth.actor(), 'course.create', entity_type='course', entity_id=course.id, entity_name=course.name,
              summary=f'Kurs angelegt: {course.name}', detail={'values': _audit_view(course)})
    db.session.commit()
    return jsonify(course.to_dict()), 201


@bp.route('/<int:cid>', methods=['PATCH'])
@auth.require_permission('schedule.edit')
def update_course(cid):
    course = _get(cid)
    before = _audit_view(course)
    for key, value in svc.read(request.get_json(silent=True) or {}, course).items():
        setattr(course, key, value)
    db.session.flush()
    db.session.expire(course)
    changes = audit.diff(before, _audit_view(course))
    if changes:
        course.updated_by = auth.actor()
        summary = f'Kurs bearbeitet: {course.name}'
        if 'instructor' in changes:
            summary = f'Dozent für {course.name}: {changes["instructor"][1] or "keiner"}'
        audit.log(auth.actor(), 'course.update', entity_type='course', entity_id=course.id,
                  entity_name=course.name, summary=summary, detail={'changes': changes})
    db.session.commit()
    return jsonify(course.to_dict())


@bp.route('/<int:cid>/participants', methods=['POST'])
@auth.require_permission('schedule.edit')
def add_participants(cid):
    course = _get(cid)
    scheduling.lock()
    added = svc.add_participants(course, (request.get_json(silent=True) or {}).get('trainee_ids'), auth.actor())
    # New participants must not already be scheduled elsewhere for the upcoming sessions.
    scheduling.check_conflicts(scheduling.future_windows(course.id), None, [t.id for t in added],
                               exclude_course_id=course.id)
    if added:
        notifications.course_joined(course, added)
        names = ', '.join(t.name for t in added)
        audit.log(auth.actor(), 'course.participants_add', entity_type='course', entity_id=course.id,
                  entity_name=course.name, summary=f'In {course.name} aufgenommen: {names}',
                  detail={'trainees': [{'id': t.id, 'name': t.name} for t in added]})
    db.session.commit()
    return jsonify({'added': [t.id for t in added]})


@bp.route('/<int:cid>/participants/<int:tid>', methods=['DELETE'])
@auth.require_permission('schedule.edit')
def remove_participant(cid, tid):
    course = _get(cid)
    row = db.session.get(CourseParticipant, (cid, tid))
    if row is None:
        raise v.NotFound('Der Kandidat ist nicht in diesem Kurs.')
    trainee = db.session.get(Trainee, tid)
    db.session.delete(row)
    audit.log(auth.actor(), 'course.participant_remove', entity_type='course', entity_id=course.id,
              entity_name=course.name, summary=f'Aus {course.name} entfernt: {trainee.name}',
              detail={'trainee': {'id': trainee.id, 'name': trainee.name}})
    db.session.commit()
    return jsonify({'removed': tid})


@bp.route('/<int:cid>/archive', methods=['POST'])
@auth.require_permission('schedule.edit')
def archive_course(cid):
    course = _get(cid)
    if not course.is_archived:
        course.archived_at, course.archived_by = utcnow(), auth.actor()
        audit.log(auth.actor(), 'course.archive', entity_type='course', entity_id=course.id,
                  entity_name=course.name, summary=f'Kurs archiviert: {course.name}')
        db.session.commit()
    return jsonify(course.to_dict())


@bp.route('/<int:cid>/restore', methods=['POST'])
@auth.require_permission('schedule.edit')
def restore_course(cid):
    course = _get(cid)
    if course.is_archived:
        svc.check_restorable(course)
        course.archived_at = course.archived_by = None
        audit.log(auth.actor(), 'course.restore', entity_type='course', entity_id=course.id,
                  entity_name=course.name, summary=f'Kurs wiederhergestellt: {course.name}')
        db.session.commit()
    return jsonify(course.to_dict())

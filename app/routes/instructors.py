"""Dozentenverwaltung: Liste, Anlegen/Bearbeiten, Archivieren."""
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import auth
from app.extensions import db
from app.models.common import utcnow
from app.models.course import Course
from app.models.instructor import Instructor
from app.models.user_role import UserRole
from app.services import audit, instructors as svc, validation as v
from app.services.permissions import INSTRUCTOR

bp = Blueprint('instructors', __name__, url_prefix='/api/instructors')

_NOT_AUDITED = ('updated_at', 'updated_by')


def _get(iid):
    instructor = db.session.get(Instructor, iid)
    if instructor is None:
        raise v.NotFound('Dozent nicht gefunden.')
    return instructor


def _audit_view(instructor):
    view = {k: val for k, val in instructor.to_dict().items() if k not in _NOT_AUDITED}
    view['levels'] = [level['name'] for level in view['levels']]
    return view


def _with_hints(rows):
    """Plus Kursanzahl und ob der Login die Rolle DOZENT hat (sonst fehlen ihm die Rechte)."""
    counts = svc.course_counts([i.id for i in rows])
    logins = [i.msh_user for i in rows if i.msh_user]
    with_role = {u for (u,) in db.session.query(UserRole.username)
                 .filter(UserRole.username.in_(logins), UserRole.role == INSTRUCTOR)} if logins else set()
    return [{**i.to_dict(), 'course_count': counts.get(i.id, 0),
             'has_instructor_role': i.msh_user in with_role if i.msh_user else None} for i in rows]


@bp.route('', methods=['GET'])
@auth.require_permission('instructor.view')
def list_instructors():
    q = Instructor.query
    q = q.filter(Instructor.archived_at.isnot(None) if request.args.get('archived') == '1'
                 else Instructor.archived_at.is_(None))
    return jsonify({'instructors': _with_hints(q.order_by(func.lower(Instructor.name)).all())})


@bp.route('/<int:iid>', methods=['GET'])
@auth.require_permission('instructor.view')
def get_instructor(iid):
    instructor = _get(iid)
    courses = (Course.query.filter(Course.instructor_id == iid, Course.archived_at.is_(None))
               .order_by(Course.name).all())
    return jsonify({'instructor': _with_hints([instructor])[0], 'courses': [c.to_dict() for c in courses]})


def _apply(instructor, data):
    # Neu (noch ohne ID): ALLE Pflichtfelder pruefen — sonst gilt es als Teil-Aenderung
    values, levels = svc.read(data, instructor if instructor.id else None)
    for key, value in values.items():
        setattr(instructor, key, value)
    if levels is not None:
        instructor.levels = levels


@bp.route('', methods=['POST'])
@auth.require_permission('instructor.manage')
def create_instructor():
    instructor = Instructor(created_by=auth.actor())
    _apply(instructor, request.get_json(silent=True) or {})
    db.session.add(instructor)
    db.session.flush()
    audit.log(auth.actor(), 'instructor.create', entity_type='instructor', entity_id=instructor.id,
              entity_name=instructor.name, summary=f'Dozent angelegt: {instructor.name}')
    db.session.commit()
    return jsonify(instructor.to_dict()), 201


@bp.route('/<int:iid>', methods=['PATCH'])
@auth.require_permission('instructor.manage')
def update_instructor(iid):
    instructor = _get(iid)
    before = _audit_view(instructor)
    _apply(instructor, request.get_json(silent=True) or {})
    changes = audit.diff(before, _audit_view(instructor))
    if changes:
        instructor.updated_by = auth.actor()
        audit.log(auth.actor(), 'instructor.update', entity_type='instructor', entity_id=instructor.id,
                  entity_name=instructor.name, summary=f'Dozent bearbeitet: {instructor.name}',
                  detail={'changes': changes})
    db.session.commit()
    return jsonify(instructor.to_dict())


@bp.route('/<int:iid>/archive', methods=['POST'])
@auth.require_permission('instructor.manage')
def archive_instructor(iid):
    instructor = _get(iid)
    if not instructor.is_archived:
        svc.check_archivable(instructor)
        instructor.archived_at, instructor.archived_by = utcnow(), auth.actor()
        audit.log(auth.actor(), 'instructor.archive', entity_type='instructor', entity_id=instructor.id,
                  entity_name=instructor.name, summary=f'Dozent archiviert: {instructor.name}')
        db.session.commit()
    return jsonify(instructor.to_dict())


@bp.route('/<int:iid>/restore', methods=['POST'])
@auth.require_permission('instructor.manage')
def restore_instructor(iid):
    instructor = _get(iid)
    if instructor.is_archived:
        instructor.archived_at = instructor.archived_by = None
        audit.log(auth.actor(), 'instructor.restore', entity_type='instructor', entity_id=instructor.id,
                  entity_name=instructor.name, summary=f'Dozent wiederhergestellt: {instructor.name}')
        db.session.commit()
    return jsonify(instructor.to_dict())

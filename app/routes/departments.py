"""Abteilungen (Teams) + Leiter: lesen (`rating.view`), pflegen (`user.manage`, gehoert zu den Zugriffsrechten).

Leiter sehen und bewerten alle aktiven Kandidaten ihrer Abteilung (`services/supervision.py`). Nie loeschen,
nur deaktivieren. Die Leiter-Logins liefert die Liste nur an `user.manage`.
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app import auth
from app.extensions import db
from app.models.department import Department
from app.models.trainee import Trainee
from app.services import audit, departments as svc, validation as v

bp = Blueprint('departments', __name__, url_prefix='/api/departments')


def _dict(department, counts, with_leaders):
    body = {**department.to_dict(), 'trainee_count': counts.get(department.id, 0)}
    if not with_leaders:
        body.pop('leaders')
    return body


@bp.route('', methods=['GET'])
@auth.require_permission('rating.view')
def list_departments():
    rows = Department.query.options(selectinload(Department.leaders)).order_by(func.lower(Department.name)).all()
    counts = dict(db.session.query(Trainee.department_id, func.count(Trainee.id))
                  .filter(Trainee.archived_at.is_(None)).group_by(Trainee.department_id))
    manage = auth.current_identity().can('user.manage')
    return jsonify({'departments': [_dict(d, counts, manage) for d in rows]})


@bp.route('', methods=['POST'])
@auth.require_permission('user.manage')
def create_department():
    values = svc.read(request.get_json(silent=True) or {})
    department = Department(created_by=auth.actor())
    db.session.add(department)
    svc.apply(department, values, auth.actor())
    db.session.flush()
    audit.log(auth.actor(), 'department.create', entity_type='department', entity_id=department.id,
              entity_name=department.name, summary=f'Abteilung angelegt: {department.name}',
              detail={'leaders': values.get('leaders', [])})
    db.session.commit()
    return jsonify(_dict(department, {}, True)), 201


@bp.route('/<int:did>', methods=['PATCH'])
@auth.require_permission('user.manage')
def update_department(did):
    department = db.session.get(Department, did)
    if department is None:
        raise v.NotFound('Abteilung nicht gefunden.')
    values = svc.read(request.get_json(silent=True) or {}, department)
    before = svc.apply(department, values, auth.actor())
    db.session.flush()
    changes = audit.diff(before, department.to_dict())
    if changes:
        audit.log(auth.actor(), 'department.update', entity_type='department', entity_id=department.id,
                  entity_name=department.name, summary=f'Abteilung geändert: {department.name}',
                  detail={'changes': changes})
    db.session.commit()
    return jsonify(_dict(department, {}, True))


_DEPT = {'id': 3, 'name': 'Erkelenz', 'active': True, 'leaders': ['galih_santoso', 'markus_weber'],
         'trainee_count': 4, 'created_at': '2026-10-09T03:00:00+00:00', 'created_by': None, 'updated_at': None,
         'updated_by': None}
DOCS = [
    {'path': '/api/departments', 'method': 'GET',
     'description': 'Abteilungen (Teams) mit Anzahl aktiver Kandidaten; `leaders` (Logins) nur mit user.manage — '
                    'rating.view',
     'response_example': {'departments': [_DEPT]}},
    {'path': '/api/departments', 'method': 'POST',
     'description': 'Abteilung anlegen, optional mit Leitern (409: Name vergeben, Login eines Kandidaten) — '
                    'user.manage',
     'request_example': {'name': 'Erkelenz', 'leaders': ['galih_santoso']}, 'response_example': _DEPT},
    {'path': '/api/departments/<id>', 'method': 'PATCH',
     'description': 'Abteilung umbenennen, (de)aktivieren, Leiter setzen (`leaders` ersetzt die Liste); Alt/Neu im '
                    'Verlauf — user.manage',
     'request_example': {'leaders': ['galih_santoso', 'markus_weber'], 'active': True},
     'response_example': _DEPT},
]

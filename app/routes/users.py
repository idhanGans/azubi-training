"""Benutzerverwaltung: Team-Rollen vergeben und entziehen (user.manage)."""
from flask import Blueprint, current_app, jsonify, request

from app import auth
from app.extensions import db
from app.models.user_role import UserRole
from app.services import access, audit, validation as v
from app.services.permissions import ASSIGNABLE_ROLES, SUPER_ADMIN

bp = Blueprint('users', __name__, url_prefix='/api/users')


@bp.route('', methods=['GET'])
@auth.require_permission('user.manage')
def list_roles():
    rows = UserRole.query.order_by(UserRole.username, UserRole.role).all()
    return jsonify({
        'assignments': [r.to_dict() for r in rows],
        'env_super_admins': sorted(current_app.config['SUPER_ADMINS']),
        'assignable_roles': list(ASSIGNABLE_ROLES),
    })


@bp.route('', methods=['POST'])
@auth.require_permission('user.manage')
def assign_role():
    data = request.get_json(silent=True) or {}
    username = v.login(data, 'username', 'MSH-Login', required=True)
    role = data.get('role')
    if role not in ASSIGNABLE_ROLES:
        raise v.ValidationError('Bitte eine gültige Rolle auswählen.', 'role')
    if access.trainee_for_login(username) is not None:
        raise v.Conflict('Dieser Login ist einem Kandidaten zugeordnet und kann keine Team-Rolle erhalten.', 'username')
    if UserRole.query.filter_by(username=username, role=role).first() is not None:
        raise v.Conflict('Dieser Login hat diese Rolle bereits.', 'role')
    row = UserRole(username=username, role=role, created_by=auth.actor())
    db.session.add(row)
    db.session.flush()
    audit.log(auth.actor(), 'role.assign', entity_type='user', entity_id=row.id,
              entity_name=username, summary=f'Rolle {role} vergeben an {username}')
    db.session.commit()
    return jsonify(row.to_dict()), 201


@bp.route('/<int:rid>', methods=['DELETE'])
@auth.require_permission('user.manage')
def revoke_role(rid):
    row = db.session.get(UserRole, rid)
    if row is None:
        raise v.NotFound('Rollenzuweisung nicht gefunden.')
    own_env_admin = auth.actor() in current_app.config['SUPER_ADMINS']
    if row.role == SUPER_ADMIN and row.username == auth.actor() and not own_env_admin:
        raise v.Conflict('Sie können sich die eigene Super-Admin-Rolle nicht selbst entziehen.')
    db.session.delete(row)
    audit.log(auth.actor(), 'role.revoke', entity_type='user', entity_id=rid,
              entity_name=row.username, summary=f'Rolle {row.role} entzogen: {row.username}')
    db.session.commit()
    return jsonify({'deleted': rid})


DOCS = [
    {'path': '/api/users', 'method': 'GET',
     'description': 'Rollenzuweisungen + Super-Admins aus der ENV + vergebbare Rollen — user.manage',
     'response_example': {'assignments': [{'id': 1, 'username': 'anna_mueller', 'role': 'HR'}],
                          'env_super_admins': ['adi_mahendra'], 'assignable_roles': list(ASSIGNABLE_ROLES)}},
    {'path': '/api/users', 'method': 'POST',
     'description': 'Rolle vergeben (409: Login ist Kandidat oder hat die Rolle schon) — user.manage',
     'request_example': {'username': 'anna_mueller', 'role': 'HR'},
     'response_example': {'id': 1, 'username': 'anna_mueller', 'role': 'HR', 'created_by': 'adi_mahendra'}},
    {'path': '/api/users/<id>', 'method': 'DELETE',
     'description': 'Rollenzuweisung entziehen (eigene Super-Admin-Rolle nicht) — user.manage',
     'request_example': {}, 'response_example': {'deleted': 1}},
]

"""Identitaet: wer ist angemeldet, mit welchen Rollen/Berechtigungen."""
from flask import Blueprint, jsonify

from app import auth
from app.models.trainee import Trainee
from app.extensions import db

bp = Blueprint('me', __name__, url_prefix='/api')


@bp.route('/me')
@auth.authenticated
def me():
    identity = auth.current_identity()
    trainee = db.session.get(Trainee, identity.trainee_id) if identity.trainee_id else None
    return jsonify({
        'user': identity.username,
        'roles': sorted(identity.roles),
        'permissions': sorted(identity.permissions),
        'trainee': trainee.public_dict() if trainee else None,
    })


@bp.route('/ping')
@auth.authenticated
def ping():
    return jsonify({'ok': True})


DOCS = [
    {'path': '/api/me', 'method': 'GET',
     'description': 'Angemeldeter Nutzer mit Rollen + Berechtigungen (Kandidat: plus eigener Teilnehmer-Datensatz)',
     'response_example': {'user': 'adi_mahendra', 'roles': ['SUPER_ADMIN'],
                          'permissions': ['audit.view', 'candidate.view'], 'trainee': None}},
    {'path': '/api/ping', 'method': 'GET',
     'description': 'Auth-Check-Endpoint (Token-geprüft) — belegt, dass die Auth greift',
     'response_example': {'ok': True}},
]

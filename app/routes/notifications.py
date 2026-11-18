"""Benachrichtigungen des angemeldeten Nutzers — nur die eigenen (Empfaenger = Login aus dem Token)."""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.notification import Notification
from app.services import notifications as svc, validation as v

bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


def _login():
    return auth.current_identity().username


@bp.route('', methods=['GET'])
@auth.authenticated
def list_notifications():
    svc.generate_due(auth.current_identity())
    rows = svc.for_user(_login(), unread_only=request.args.get('unread') == '1')
    return jsonify({'notifications': [n.to_dict() for n in rows], 'unread': svc.unread_count(_login()),
                    'limit': svc.LIST_LIMIT})


@bp.route('/count', methods=['GET'])
@auth.authenticated
def count():
    svc.generate_due(auth.current_identity())
    return jsonify({'unread': svc.unread_count(_login())})


@bp.route('/<int:nid>/read', methods=['POST'])
@auth.authenticated
def read_one(nid):
    if Notification.query.filter_by(id=nid, recipient=_login()).first() is None:
        raise v.NotFound('Benachrichtigung nicht gefunden.')      # fremde verraten nicht, dass es sie gibt
    svc.mark_read(_login(), nid)
    db.session.commit()
    return jsonify({'unread': svc.unread_count(_login())})


@bp.route('/read-all', methods=['POST'])
@auth.authenticated
def read_all():
    changed = svc.mark_read(_login())
    db.session.commit()
    return jsonify({'marked': changed, 'unread': 0})


_N = {'id': 12, 'type': 'SESSION_REMINDER', 'link': '/my-schedule', 'read': False, 'read_at': None,
      'created_at': '2026-09-25T08:00:00+00:00',
      'params': {'course': 'Sprechkurs B1', 'date': '2026-09-26', 'start': '10:00', 'end': '12:00', 'room': 'R 1.02'}}
DOCS = [
    {'path': '/api/notifications', 'method': 'GET',
     'description': 'Eigene Benachrichtigungen (neueste zuerst, max. 100; ?unread=1 nur ungelesene) + Anzahl '
                    'ungelesen. Arten: SESSION_REMINDER, SESSION_CANCELLED, SESSION_MOVED, COURSE_JOINED, '
                    'ASSESSMENT_PUBLISHED, ASSESSMENT_CORRECTED, ASSESSMENT_DRAFT_OPEN, ATTENDANCE_MISSING; den Text '
                    'baut die Oberfläche aus type + params. Fällige Erinnerungen entstehen beim Abruf — angemeldet',
     'response_example': {'notifications': [_N], 'unread': 3, 'limit': 100}},
    {'path': '/api/notifications/count', 'method': 'GET',
     'description': 'Anzahl ungelesener eigener Benachrichtigungen (für die Glocke) — angemeldet',
     'response_example': {'unread': 3}},
    {'path': '/api/notifications/<id>/read', 'method': 'POST',
     'description': 'Eine eigene Benachrichtigung als gelesen markieren (fremde: 404) — angemeldet',
     'request_example': {}, 'response_example': {'unread': 2}},
    {'path': '/api/notifications/read-all', 'method': 'POST',
     'description': 'Alle eigenen als gelesen markieren — angemeldet', 'request_example': {},
     'response_example': {'marked': 3, 'unread': 0}},
]

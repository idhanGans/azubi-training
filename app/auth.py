"""Authentication + central access check (Zugriffspruefung) — for EVERY request.

1. Authentication: every request (except /health, /docs, static files)
   runs through `msh_base.require_msh_auth` — the token is verified. The
   identity comes from the token, NEVER from an `X-Auth-*` header (that
   can be forged cluster-internally).
2. Authorization: every route DECLARES via decorator who may use it;
   `_enforce` checks that here in exactly one place. A route without a rule is
   locked (default-deny), `tests/test_rbac.py` checks all routes against this.
3. CSRF: write requests must carry `Content-Type: application/json`
   OR (file uploads, multipart) the header `X-Requested-With: fetch`. A foreign
   page without CORS approval can send neither (a form POST arrives as
   form/text without its own headers) — the auth cookie alone is never enough.
4. Who changed it: before every write to the DB, `_stamp_actor` sets `created_by`
   on new rows and `updated_by` on changed rows to the logged-in login — for every table with
   these columns, even if a route forgets it (`updated_at` is set by the model via `onupdate`).
"""
from flask import current_app, g, has_request_context, jsonify, render_template, request
from sqlalchemy import event
from sqlalchemy.orm import Session
from msh_base import require_msh_auth
from msh_base.health import HEALTH_BLUEPRINT_NAME

from app.services import access

ACCESS_ATTR = '_access_rule'
_PUBLIC_ENDPOINTS = {'static'}
_WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def _mark(rule):
    def decorate(view):
        setattr(view, ACCESS_ATTR, rule)
        return view
    return decorate


def require_permission(permission):
    """Route only for users with this permission (`services/permissions.py`)."""
    return _mark(('permission', permission))


#: Route only for candidates (Kandidaten) — it returns exclusively their OWN data.
candidate_only = _mark(('candidate', None))

#: Route only for users whose login is attached to an instructor (Dozent) — their own courses.
instructor_only = _mark(('instructor', None))

#: Route for every logged-in user, even without a role (e.g. "who am I").
authenticated = _mark(('authenticated', None))


def is_allowed(rule, identity):
    kind, value = rule
    if kind == 'authenticated':
        return bool(identity.username)
    if kind == 'candidate':
        return identity.is_candidate and identity.trainee_id is not None
    if kind == 'instructor':
        return identity.instructor_id is not None
    if kind == 'permission':
        return identity.can(value)
    return False


def rule_for(endpoint):
    view = current_app.view_functions.get(endpoint)
    return getattr(view, ACCESS_ATTR, None) if view else None


def current_identity():
    return g.identity


def actor():
    """Verified login of the current user — for audit log entries."""
    return g.identity.username


def _is_public(endpoint):
    return endpoint in _PUBLIC_ENDPOINTS or endpoint.startswith(HEALTH_BLUEPRINT_NAME + '.')


_verify_token = require_msh_auth(lambda: None)


def _deny(status=403):
    identity = g.get('identity')
    current_app.logger.warning('Zugriff verweigert: %s %s %s', identity.username if identity else '-',
                               request.method, request.path)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Sie haben keine Berechtigung für diese Aktion.',
                        'code': 'FORBIDDEN'}), status
    return render_template('pages/no_access.html', page_title='Kein Zugriff',
                           page_i18n='noaccess_title'), status


def _enforce():
    endpoint = request.endpoint
    if endpoint is not None and _is_public(endpoint):
        return None
    rejected = _verify_token()
    if rejected is not None:
        return rejected
    if request.method in _WRITE_METHODS and not (
            request.is_json or request.headers.get('X-Requested-With') == 'fetch'):
        return jsonify({'error': 'Die Anfrage muss als JSON gesendet werden.',
                        'code': 'JSON_REQUIRED'}), 415
    if request.method in _WRITE_METHODS and request.is_json and request.content_length:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):      # list, number, text or broken JSON: never pass to the routes
            return jsonify({'error': 'Der Inhalt muss ein JSON-Objekt sein.', 'code': 'JSON_OBJECT_REQUIRED'}), 400
    username = (request.msh_user or {}).get('username')
    g.identity = access.resolve(username, current_app.config['SUPER_ADMINS'])
    if endpoint is None:
        return None  # unknown path -> Flask responds 404
    rule = rule_for(endpoint)
    if rule is None:
        current_app.logger.error('Route ohne Zugriffsregel gesperrt: %s', endpoint)
        return _deny()
    if not is_allowed(rule, g.identity):
        return _deny()
    return None


def _stamp_actor(session, _context, _instances):
    if not has_request_context() or getattr(g, 'identity', None) is None:
        return
    login = g.identity.username
    for obj in session.new:
        if hasattr(obj, 'created_by') and obj.created_by is None:
            obj.created_by = login
    for obj in session.dirty:
        if hasattr(obj, 'updated_by') and session.is_modified(obj, include_collections=False):
            obj.updated_by = login


def init_app(app):
    if not event.contains(Session, 'before_flush', _stamp_actor):
        event.listen(Session, 'before_flush', _stamp_actor)
    app.before_request(_enforce)

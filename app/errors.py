"""Error responses in German: API as JSON (with `field` on input errors), pages as an error page.
Never a stack trace or internal text to the outside — that only goes into the log."""
from flask import jsonify, render_template, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.extensions import db
from app.services.validation import ValidationError


def register(app):
    @app.errorhandler(ValidationError)
    def _invalid(err):
        db.session.rollback()
        body = {'error': err.message, 'field': err.field}
        if err.details is not None:
            body['details'] = err.details
        return jsonify(body), err.status

    @app.errorhandler(RequestEntityTooLarge)
    def _too_large(_err):
        mb = app.config['MAX_UPLOAD_BYTES'] // (1024 * 1024)
        if request.path.startswith('/api/'):
            return jsonify({'error': f'Die Datei ist zu groß (höchstens {mb} MB).', 'field': 'file'}), 413
        return f'Die Datei ist zu groß (höchstens {mb} MB).', 413

    @app.errorhandler(IntegrityError)
    def _integrity(err):
        """A database rule has kicked in (UNIQUE, foreign key, CHECK). The application checks
        beforehand itself — only what happened concurrently (two create the same name)
        or what the check missed ends up here. Nothing is saved, the response is 409/400 instead of 500."""
        db.session.rollback()
        code = getattr(err.orig, 'pgcode', None)
        constraint = getattr(getattr(err.orig, 'diag', None), 'constraint_name', None)
        app.logger.warning('DB-Regel %s (%s) bei %s %s', constraint, code, request.method, request.path)
        status, message = DB_RULES.get(code, (400, MESSAGES[400]))
        if request.path.startswith('/api/'):
            return jsonify({'error': message, 'code': 'DB_RULE'}), status
        return _respond(status)

    @app.errorhandler(HTTPException)
    def _http_error(err):
        """404/405/… in German — API as JSON, pages as their own error page."""
        return _respond(err.code)

    @app.errorhandler(Exception)
    def _unexpected(err):
        """Unexpected error: into the log (with stack trace), only a generic sentence to the outside."""
        db.session.rollback()
        app.logger.exception('Unerwarteter Fehler bei %s %s', request.method, request.path)
        return _respond(500)


#: Messages per status — no technical details to the outside.
MESSAGES = {
    400: 'Die Anfrage ist ungültig.',
    401: 'Bitte melden Sie sich an.',
    403: 'Sie haben keine Berechtigung für diese Aktion.',
    404: 'Die Seite oder der Datensatz wurde nicht gefunden.',
    405: 'Diese Aktion ist hier nicht möglich.',
    415: 'Die Anfrage muss als JSON gesendet werden.',
    429: 'Zu viele Anfragen — bitte kurz warten.',
    500: 'Ein interner Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.',
}


#: Postgres error code -> (status, message) for violated database rules.
DB_RULES = {
    '23505': (409, 'Diesen Eintrag gibt es bereits — vermutlich wurde er gerade gleichzeitig angelegt. '
                   'Bitte laden Sie die Seite neu.'),
    '23503': (409, 'Der Datensatz wird noch verwendet oder wurde inzwischen entfernt. Bitte laden Sie die Seite neu.'),
    '23514': (400, 'Ein Wert liegt außerhalb des erlaubten Bereichs.'),
    '23502': (400, 'Ein Pflichtfeld fehlt.'),
}


def _respond(status):
    message = MESSAGES.get(status) or MESSAGES[500 if status >= 500 else 400]
    if request.path.startswith('/api/'):
        return jsonify({'error': message, 'code': f'HTTP_{status}'}), status
    return render_template('pages/error.html', page_title='Fehler', page_i18n='err_page_title', status=status,
                           message=message), status

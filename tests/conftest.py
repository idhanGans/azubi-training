"""Shared setup for this service's tests.

- Repo root on `sys.path`, so `from app import create_app` works.
- The tests run against a REAL Postgres (the DB is not mocked).
  Address from `TEST_DATABASE_URL`, default is the local test DB from the
  CLAUDE.md (section "Tests"). `DATABASE_URL` is ALWAYS set to it —
  this way a prod/sandbox DB from the environment can never be wiped; additionally
  the DB name must end in `_test`.
- Only the EXTERNAL auth counterpart (user-handling) is replaced: the token is
  simply the login name in the test. The app logic in front of it (`app/auth.py`) runs for real.
"""
import json as _json
import os
import sys
import tempfile

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DB = os.environ.get('TEST_DATABASE_URL', 'postgresql://postgres@127.0.0.1:55432/azubi_test')
assert make_url(TEST_DB).database.endswith('_test'), 'Test-DB muss auf _test enden'
os.environ['DATABASE_URL'] = TEST_DB
os.environ['MSH_AUTO_MIGRATE'] = 'False'
os.environ['MSH_LOGIN_URL'] = 'https://login.example/login'
os.environ['MSH_AUTH_URL'] = 'http://auth.invalid/verify'
os.environ['SUPER_ADMINS'] = 'root_admin'
os.environ['UPLOAD_DIR'] = tempfile.mkdtemp(prefix='azubi-uploads-')
os.environ['MAX_UPLOAD_MB'] = '1'

import msh_base.auth as msh_auth  # noqa: E402

_TABLES = ('activity_log', 'notification', 'assessment_score', 'assessment', 'assessment_criterion', 'assessment_category',
           'assessment_template', 'leiter_rating', 'training_report', 'trainee', 'user_role',
           'candidate_status', 'language_level', 'program', 'curriculum', 'course_module', 'material',
           'instructor', 'instructor_level', 'course', 'course_participant', 'course_session', 'attendance', 'lesson_rating',
           'staff_rating', 'department_leader', 'department')


def _load_migration(filename):
    """Initial values come from the migration itself — there is only ONE list."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'migrations', 'versions', filename)
    spec = importlib.util.spec_from_file_location(filename[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SEEDS = _load_migration('0004_candidate_management.py')


def _reset(session):
    session.execute(text(f'TRUNCATE {", ".join(_TABLES)} RESTART IDENTITY CASCADE'))
    session.execute(text('ALTER SEQUENCE candidate_no_seq RESTART'))
    for table, rows in (('candidate_status', _SEEDS.STATUSES),
                        ('language_level', [(c, c) for c in _SEEDS.LEVELS])):
        for i, (code, name) in enumerate(rows):
            session.execute(text(f'INSERT INTO {table} (code, name, sort_order) VALUES (:c, :n, :o)'),
                            {'c': code, 'n': name, 'o': (i + 1) * 10})
    session.commit()


def _fake_verify(token):
    if token == 'kaputt':
        return None, msh_auth.AUTH_INVALID
    return {'user_id': 1, 'username': token, 'role': 'developer'}, msh_auth.AUTH_OK


@pytest.fixture(scope='session')
def app():
    from flask_migrate import upgrade
    from app import create_app
    from app.extensions import db
    application = create_app()
    application.config['TESTING'] = True
    with application.app_context():
        try:
            db.session.execute(text('SELECT 1'))
        except Exception as exc:  # noqa: BLE001 — clear skip message instead of traceback
            pytest.skip(f'Test-Postgres nicht erreichbar ({TEST_DB}): {exc.__class__.__name__}')
        db.session.execute(text('DROP SCHEMA public CASCADE; CREATE SCHEMA public'))
        db.session.commit()
        upgrade()
    return application


@pytest.fixture(autouse=True)
def _fake_auth(monkeypatch):
    monkeypatch.setattr(msh_auth, '_verify_token', _fake_verify)


@pytest.fixture
def db(app):
    from app.extensions import db as _db
    with app.app_context():
        yield _db
        _db.session.rollback()
        _reset(_db.session)


class Client:
    """Test client that acts as a specific login (Bearer token = login)."""

    def __init__(self, flask_client, username):
        self._c = flask_client
        self._headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        if username:
            self._headers['Authorization'] = f'Bearer {username}'

    def _call(self, method, url, json=None, headers=None):
        return self._c.open(url, method=method, headers={**self._headers, **(headers or {})},
                            data=None if json is None else _json.dumps(json))

    def get(self, url, **kw):
        return self._call('GET', url, **kw)

    def post(self, url, json=None, **kw):
        return self._call('POST', url, json=json if json is not None else {}, **kw)

    def patch(self, url, json=None, **kw):
        return self._call('PATCH', url, json=json, **kw)

    def put(self, url, json=None, **kw):
        return self._call('PUT', url, json=json, **kw)

    def delete(self, url, **kw):
        return self._call('DELETE', url, **kw)

    def upload(self, url, fields, file_name=None, content=b'', csrf_header=True):
        """multipart upload like from the browser (with X-Requested-With: fetch)."""
        import io
        data = dict(fields)
        if file_name is not None:
            data['file'] = (io.BytesIO(content), file_name)
        headers = {k: v for k, v in self._headers.items() if k != 'Content-Type'}
        if csrf_header:
            headers['X-Requested-With'] = 'fetch'
        return self._c.post(url, data=data, headers=headers, content_type='multipart/form-data')


@pytest.fixture
def as_user(app, db):
    """`as_user('anna')` -> client logged in as login `anna` (None = without token)."""
    return lambda username: Client(app.test_client(), username)


@pytest.fixture
def grant(db):
    """`grant('anna', 'HR')` creates a team role directly in the DB."""
    from app.models.user_role import UserRole

    def _grant(username, role):
        db.session.add(UserRole(username=username, role=role, created_by='test'))
        db.session.commit()
    return _grant


@pytest.fixture
def trainee(db):
    """`trainee('Budi', msh_user='budi')` creates a participant and returns its ID."""
    from app.models.trainee import Trainee

    def _trainee(name, **fields):
        row = Trainee(name=name, **fields)
        db.session.add(row)
        db.session.commit()
        return row.id
    return _trainee

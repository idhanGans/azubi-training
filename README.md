# Azubi-Training

Training monitoring and German-course management for apprentice candidates (Azubis): candidates, instructors,
courses, timetable, attendance, assessments, module ratings, progress, candidate portal, dashboard, reports,
staff ratings per program month, overall rating with month comparison, curriculum with learning material.
UI in German with English/Indonesian switcher.

Flask 3 + SQLAlchemy + Alembic + PostgreSQL, Jinja pages with vanilla JS (no build step). Structure and rules:
`CLAUDE.md`.

## About this copy

This is a sanitized source export:

- No git history, no data, no uploads, no credentials (secrets were never in the code; they come from the
  hosting platform as environment variables).
- Names and logins of real people in tests and API examples were replaced with invented ones.
- `SUPER_ADMINS` in `msh_config.json` is empty — set your own admin login(s) there.
- The platform library `msh_base` (login/token check, health endpoint) is not included. The app imports it in
  `app/auth.py` and `app/__init__.py`; to run the app elsewhere, replace it with your own token verification.

## Tests

Real PostgreSQL (database name must end in `_test`):

```bash
pip install -r requirements.txt
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/azubi_test python3 -m pytest -q
```

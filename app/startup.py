"""Schema-Migration beim App-Start (k3s-Pattern).

Serialisiert ueber einen Postgres Session-Advisory-Lock — mehrere Worker/
Replicas migrieren sonst gleichzeitig.
"""
from flask_migrate import upgrade
from sqlalchemy import text

from app.extensions import db

_LOCK_KEY = 0x4D5348  # "MSH"


def auto_migrate(app):
    with app.app_context():
        try:
            conn = db.engine.connect()
            try:
                conn.execute(text('SELECT pg_advisory_lock(:k)'), {'k': _LOCK_KEY})
                upgrade()
            finally:
                conn.execute(text('SELECT pg_advisory_unlock(:k)'), {'k': _LOCK_KEY})
                conn.close()
        except Exception:
            app.logger.exception('Auto-Migration fehlgeschlagen')
            raise

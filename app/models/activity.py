from app.extensions import db
from app.models.common import iso, utcnow


class ActivityLog(db.Model):
    """Audit trail (append-only): ONE entry per mutating action.

    Immutable: a database trigger (migration 0012) rejects UPDATE and
    DELETE — there is only INSERT (`app/services/audit.py`).

    Records WHO (actor = verified MSH login), WHEN, WHAT (action +
    entity) and a human-readable summary. On changes, `detail` carries
    the field diffs `{"changes": {field: [old, new]}}`. Names are stored
    as a snapshot so the entry stays readable after a rename.
    """
    __tablename__ = 'activity_log'
    # indexes from migration 0012 — declared here so an autogenerate does not drop them again
    __table_args__ = (db.Index('ix_activity_log_entity', 'entity_type', 'entity_id'),
                      db.Index('ix_activity_log_actor', 'actor'))

    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(120), nullable=True)                    # MSH username
    action = db.Column(db.String(80), nullable=False, index=True)       # e.g. trainee.delete
    entity_type = db.Column(db.String(30), nullable=True, index=True)   # trainee
    entity_id = db.Column(db.Integer, nullable=True)
    entity_name = db.Column(db.String(200), nullable=True)              # snapshot
    summary = db.Column(db.String(400), nullable=True)                  # human-readable
    detail = db.Column(db.JSON, nullable=True)
    reason = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id, 'actor': self.actor or 'unbekannt', 'action': self.action,
            'entity_type': self.entity_type, 'entity_id': self.entity_id,
            'entity_name': self.entity_name, 'summary': self.summary,
            'detail': self.detail, 'reason': self.reason,
            'changes': flatten_changes((self.detail or {}).get('changes')),
            'created_at': iso(self.created_at),
        }


def flatten_changes(changes, prefix=''):
    """`{field: [old, new]}` (also nested) -> `[{field, old, new}]` — one row per changed value.

    Whole structures (e.g. all categories of a template) are not expanded:
    `structure: True`, the details remain in `detail`.
    """
    rows = []
    for field, value in (changes or {}).items():
        name = f'{prefix}{field}'
        if isinstance(value, list) and len(value) == 2 and not any(isinstance(v, dict) for v in value):
            rows.append({'field': name, 'old': value[0], 'new': value[1]})
        elif isinstance(value, dict):
            rows.extend(flatten_changes(value, f'{name} › '))
        else:
            rows.append({'field': name, 'old': None, 'new': None, 'structure': True})
    return rows

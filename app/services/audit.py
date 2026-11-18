"""Audit trail: `log(...)` attaches an ActivityLog entry to the CURRENT
session. The caller does the COMMIT — the log entry and the business
change thus live in ONE transaction (both or neither).
"""
from app.extensions import db
from app.models.activity import ActivityLog


def de_number(num):
    """6.5 -> '6,5'."""
    return f'{num:g}'.replace('.', ',')


#: Row bookkeeping (who/when last) — already present in the entry itself, not a content change.
_META = ('updated_at', 'updated_by')


def diff(before, after):
    """Field diff of two dicts: only changed fields, as {field: [old, new]} (without `updated_at/_by`)."""
    return {k: [before.get(k), after.get(k)] for k in after if k not in _META and before.get(k) != after.get(k)}


def _fit(text, column):
    """Truncate to the column length (with "..."). Long enumerations — e.g. 24 names for a
    course enrollment — appear in full in `detail`; the text must never make the change fail."""
    limit = column.type.length
    return text if text is None or len(text) <= limit else text[:limit - 1].rstrip() + '…'


def log(actor, action, entity_type=None, entity_id=None, entity_name=None,
        summary=None, detail=None, reason=None):
    """Create an audit entry (caller commits)."""
    db.session.add(ActivityLog(
        actor=actor, action=action, entity_type=entity_type,
        entity_id=entity_id, entity_name=_fit(entity_name, ActivityLog.entity_name),
        summary=_fit(summary, ActivityLog.summary), detail=detail, reason=(reason or None),
    ))

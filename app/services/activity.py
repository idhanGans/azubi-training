"""Verlauf lesen (die Schreib-Seite ist audit.py): Filter, Seiten (before_id), Auswahllisten, Anzeigenamen."""
from sqlalchemy import func, or_

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.instructor import Instructor
from app.models.trainee import Trainee
from app.services.local_time import day_range_utc


def actor_names(logins):
    """Login -> Anzeigename (Dozent oder Kandidat mit diesem Login), sonst fehlt der Login im Ergebnis."""
    logins = [x for x in logins if x]
    if not logins:
        return {}
    names = dict(db.session.query(Trainee.msh_user, Trainee.name).filter(Trainee.msh_user.in_(logins)))
    names.update(db.session.query(Instructor.msh_user, Instructor.name).filter(Instructor.msh_user.in_(logins)))
    return names


def search(*, actor=None, action=None, entity_type=None, entity_id=None, first=None, last=None, text=None,
           before_id=None, limit=100):
    """Neueste zuerst. `action` „assessment" findet assessment.*, „assessment.correct" genau diese Aktion.
    Liefert (Eintraege mit actor_name, next_before_id fuer die naechste Seite oder None)."""
    q = ActivityLog.query
    if entity_type:
        q = q.filter(ActivityLog.entity_type == entity_type)
    if actor:
        q = q.filter(ActivityLog.actor == actor)
    if action:
        q = q.filter(or_(ActivityLog.action == action, ActivityLog.action.like(f'{action}.%')))
    if entity_id:
        q = q.filter(ActivityLog.entity_id == entity_id)
    if first:
        q = q.filter(ActivityLog.created_at >= day_range_utc(first, first)[0])
    if last:
        q = q.filter(ActivityLog.created_at < day_range_utc(last, last)[1])
    if text:
        like = f'%{text.replace("%", "").replace("_", "")}%'
        q = q.filter(or_(ActivityLog.summary.ilike(like), ActivityLog.entity_name.ilike(like),
                         ActivityLog.actor.ilike(like), ActivityLog.reason.ilike(like)))
    if before_id:
        q = q.filter(ActivityLog.id < before_id)
    rows = q.order_by(ActivityLog.id.desc()).limit(limit + 1).all()
    more = len(rows) > limit
    rows = rows[:limit]
    names = actor_names({r.actor for r in rows})
    return [{**r.to_dict(), 'actor_name': names.get(r.actor)} for r in rows], (rows[-1].id if more else None)


def facets():
    """Auswahllisten fuer die Filter: wer hat etwas getan, welche Aktionen und Datensatz-Arten gibt es."""
    actors = [a for (a,) in db.session.query(ActivityLog.actor).filter(ActivityLog.actor.isnot(None))
              .group_by(ActivityLog.actor).order_by(func.lower(ActivityLog.actor))]
    actions = [a for (a,) in db.session.query(ActivityLog.action).group_by(ActivityLog.action).order_by(ActivityLog.action)]
    entity_types = [e for (e,) in db.session.query(ActivityLog.entity_type).filter(ActivityLog.entity_type.isnot(None))
                    .group_by(ActivityLog.entity_type).order_by(ActivityLog.entity_type)]
    names = actor_names(actors)
    return {'actors': [{'login': a, 'name': names.get(a)} for a in actors], 'actions': actions,
            'entity_types': entity_types}

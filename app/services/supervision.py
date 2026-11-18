"""Assignment SPV/leader -> candidates: WHOM a login may rate and see in the overall rating.

- SPV (supervisor): the active candidates with `trainee.supervisor` = login.
- Leader: all active candidates of the departments they lead (`department_leader`).
- Internal team (`rating.internal`): rates every active candidate — kind INTERN.
Whoever is both (e.g. SPV and internal team) rates "their" candidates as SPV/leader.

The overall rating is fully visible to whoever has `report.view`; everyone else sees only their assignment.
Archived candidates never count.
"""
from sqlalchemy import or_, select

from app.extensions import db
from app.models.department_leader import DepartmentLeader
from app.models.trainee import Trainee

SPV, LEITER, INTERN = 'SPV', 'LEITER', 'INTERN'
#: Kinds that together form the part "SPV feedback" of the overall rating.
SUPERVISOR_KINDS = (SPV, LEITER)


def _led(login):
    return select(DepartmentLeader.department_id).where(DepartmentLeader.username == login)


def assigned_condition(login):
    """SQL condition on `Trainee`: assigned as SPV or leader (without archive filter)."""
    return or_(Trainee.supervisor == login, Trainee.department_id.in_(_led(login)))


def assigned_ids(login):
    """Subquery of the active candidates the login is assigned to as SPV or leader."""
    return select(Trainee.id).where(assigned_condition(login), Trainee.archived_at.is_(None))


def leads(login):
    """IDs of the departments the login leads."""
    return {d for (d,) in db.session.execute(_led(login))}


def kind_for(identity, trainee, led=None):
    """As what does `identity` rate this candidate? SPV / LEITER / INTERN — None = not at all."""
    if trainee is None or trainee.is_archived:
        return None
    if trainee.supervisor == identity.username:
        return SPV
    if trainee.department_id is not None and trainee.department_id in (leads(identity.username) if led is None
                                                                      else led):
        return LEITER
    if identity.can('rating.internal'):
        return INTERN
    return None


def rateable_condition(identity):
    """SQL condition on `Trainee` for the rating overview — None = all active ones."""
    if identity.can('rating.internal'):
        return None
    return assigned_condition(identity.username)


def visible_condition(identity):
    """SQL condition on `Trainee` for the overall rating — None = all active ones (`report.view`)."""
    if identity.can('report.view'):
        return None
    return assigned_condition(identity.username)


def can_see(identity, trainee):
    """Is the overall rating of this candidate visible?"""
    if trainee is None or trainee.is_archived:
        return False
    return identity.can('report.view') or kind_for(identity, trainee) in SUPERVISOR_KINDS

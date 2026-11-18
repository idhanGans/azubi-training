"""Wer ist der angemeldete Nutzer in DIESER App? (Rollen + Berechtigungen)

Eingabe ist immer der VERIFIZIERTE MSH-Login (aus dem Token, siehe
`app/auth.py`) — nie ein Header. Regeln:

1. Haengt der Login an einem Teilnehmer, ist er KANDIDAT — und nur das. Ein
   archivierter Teilnehmer hat gar keine Rolle mehr (kein Rueckfall auf Team).
2. Sonst gelten die Rollen aus `user_role`, plus SUPER_ADMIN fuer die Logins
   aus der ENV `SUPER_ADMINS`. Haengt der Login an einem (nicht archivierten)
   Dozenten, traegt die Identitaet dessen ID (`instructor_id`).
3. Wer sonst keine Rolle hat, ist MITARBEITER (`EVALUATOR`): er darf nur Kandidaten bewerten
   (Mitarbeiter-Bewertung). In die App kommt ohnehin nur, wer das ZV-Flag `view` hat.
"""
from dataclasses import dataclass, field

from sqlalchemy import func

from app.models.instructor import Instructor
from app.models.trainee import Trainee
from app.models.user_role import UserRole
from app.services.permissions import CANDIDATE, EVALUATOR, SUPER_ADMIN, permissions_for


@dataclass(frozen=True)
class Identity:
    username: str
    roles: frozenset = field(default_factory=frozenset)
    permissions: frozenset = field(default_factory=frozenset)
    trainee_id: int | None = None
    instructor_id: int | None = None

    @property
    def is_candidate(self):
        return CANDIDATE in self.roles

    def can(self, permission):
        return permission in self.permissions


def trainee_for_login(username):
    """Teilnehmer (auch archiviert), an dem dieser Login haengt — oder None."""
    return Trainee.query.filter(func.lower(Trainee.msh_user) == username.lower()).first()


def resolve(username, super_admins):
    username = (username or '').strip().lower()
    if not username:
        return Identity(username='')
    trainee = trainee_for_login(username)
    if trainee is not None:
        if trainee.is_archived:
            return Identity(username=username)
        return Identity(username=username, roles=frozenset({CANDIDATE}),
                        trainee_id=trainee.id)
    roles = {r.role for r in UserRole.query.filter_by(username=username)}
    if username in super_admins:
        roles.add(SUPER_ADMIN)
    if not roles:
        roles.add(EVALUATOR)
    instructor = Instructor.query.filter(Instructor.msh_user == username,
                                         Instructor.archived_at.is_(None)).first()
    return Identity(username=username, roles=frozenset(roles),
                    permissions=permissions_for(roles),
                    instructor_id=instructor.id if instructor else None)

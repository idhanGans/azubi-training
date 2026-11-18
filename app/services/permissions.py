"""Roles and permissions — THE ONE place that defines what each role may do.

Routes only declare the permission they need
(`app/auth.py::require_permission`); it is checked centrally before every request.
A new permission goes here AND into the roles that should get it.

`candidate.view_all` is the scope (Reichweite) of `candidate.view`/`schedule.view`
etc.: whoever lacks it only sees the candidates of their own courses.

`rating.view`/`rating.create` (rating by SPV/leader, overall rating) is held by EVERY login except candidates:
WHO someone sees and rates is decided by the assignment (`services/supervision.py`: SPV for their own
candidates, leader for their own departments). `rating.internal` (internal team) additionally rates every
active candidate.
"""
SUPER_ADMIN = 'SUPER_ADMIN'
HR = 'HR'
ACADEMIC_MANAGER = 'ACADEMIC_MANAGER'
INSTRUCTOR = 'INSTRUCTOR'
MANAGEMENT = 'MANAGEMENT'
CANDIDATE = 'CANDIDATE'
#: Staff member without a team role (every login that reaches the app): may only rate and see the
#: overall rating — both only for the candidates they are assigned to as SPV or leader.
#: Not assigned, but derived in `access.resolve` — like CANDIDATE.
EVALUATOR = 'EVALUATOR'

#: Roles that a super admin assigns in user management. CANDIDATE is
#: deliberately not among them — it is derived from the link to a participant.
ASSIGNABLE_ROLES = (SUPER_ADMIN, HR, ACADEMIC_MANAGER, INSTRUCTOR, MANAGEMENT)

ALL_PERMISSIONS = frozenset({
    'candidate.view', 'candidate.view_all', 'candidate.create', 'candidate.edit',
    'instructor.view', 'instructor.manage',
    'assessment.view', 'assessment.create', 'assessment.edit', 'assessment.configure',
    'curriculum.view', 'curriculum.create', 'curriculum.edit',
    'schedule.view', 'schedule.create', 'schedule.edit',
    'attendance.view', 'attendance.manage',
    'report.view', 'rating.view', 'rating.create', 'rating.internal',
    'note.edit',
    'user.manage', 'system.manage', 'audit.view',
})

_RATE = frozenset({'rating.view', 'rating.create'})

_READ_ALL = frozenset({
    'candidate.view', 'candidate.view_all', 'assessment.view', 'curriculum.view',
    'schedule.view', 'attendance.view', 'instructor.view',
}) | _RATE

ROLE_PERMISSIONS = {
    SUPER_ADMIN: ALL_PERMISSIONS,
    HR: _READ_ALL | {'candidate.create', 'candidate.edit', 'instructor.manage', 'report.view', 'rating.internal'},
    ACADEMIC_MANAGER: _READ_ALL | {
        'candidate.edit', 'instructor.manage', 'assessment.create', 'assessment.edit', 'assessment.configure',
        'curriculum.create', 'curriculum.edit', 'schedule.create', 'schedule.edit',
        'attendance.manage', 'report.view',
    },
    # Without `candidate.view_all`: instructors only see candidates and courses of
    # THEIR OWN courses (`app/services/scope.py`).
    INSTRUCTOR: frozenset({
        'candidate.view', 'assessment.view', 'assessment.create', 'assessment.edit',
        'curriculum.view', 'schedule.view', 'attendance.view', 'attendance.manage',
    }) | _RATE,
    MANAGEMENT: _READ_ALL | {'report.view'},
    EVALUATOR: _RATE,
    # Candidates have NONE of these permissions: they exclusively reach
    # their own data via the routes marked with `candidate_only`.
    CANDIDATE: frozenset(),
}


def permissions_for(roles):
    """Union of the permissions of all roles."""
    result = set()
    for role in roles:
        result |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(result)

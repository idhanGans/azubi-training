"""Create/edit candidates (incl. field and cross-field validation)."""
from datetime import date

from sqlalchemy import func

from app.models.candidate_status import CandidateStatus
from app.models.department import Department
from app.models.instructor import Instructor
from app.models.language_level import LanguageLevel
from app.models.program import Program
from app.models.trainee import Trainee
from app.models.user_role import UserRole
from app.services import local_time, validation as v

FACH_OPTIONS = ('Elektro', 'SHK')
_EARLIEST_BIRTH = date(1950, 1, 1)
_TEXT_FIELDS = (('name', 'Name', 200), ('nickname', 'Rufname', 120), ('abteilung', 'Abteilung', 80),
                ('target_occupation', 'Ausbildungsberuf', 120))


def _read(data, trainee):
    """Only read the fields that were sent (PATCH) — when creating, trainee is None."""
    has = (lambda key: key in data) if trainee else (lambda key: True)
    values = {}
    for name, label, max_len in _TEXT_FIELDS:
        if has(name):
            values[name] = v.text(data, name, label, max_len, required=(name == 'name'))
    if has('email'):
        values['email'] = v.email(data, 'email', 'E-Mail')
    if has('phone'):
        values['phone'] = v.phone(data, 'phone', 'Telefon')
    if has('fach'):
        fach = v.text(data, 'fach', 'Fachrichtung', 20)
        if fach is not None and fach not in FACH_OPTIONS:
            raise v.ValidationError('Bitte eine gültige Fachrichtung auswählen.', 'fach')
        values['fach'] = fach
    if has('date_of_birth'):
        values['date_of_birth'] = v.day(data, 'date_of_birth', 'Geburtsdatum',
                                        earliest=_EARLIEST_BIRTH, latest=local_time.today())
    for name, label in (('start_date', 'Beginn'), ('expected_completion_date', 'Voraussichtliches Ende')):
        if has(name):
            values[name] = v.day(data, name, label)
    for name, label, model in (('program_id', 'Programm', Program),
                               ('status_id', 'Status', CandidateStatus),
                               ('department_id', 'Abteilung', Department),
                               ('current_level_id', 'Aktuelles Sprachniveau', LanguageLevel),
                               ('target_level_id', 'Ziel-Sprachniveau', LanguageLevel)):
        if has(name):
            row = v.reference(data, name, label, model, getattr(trainee, name, None))
            values[name] = row.id if row else None
    if has('msh_user'):
        values['msh_user'] = v.login(data, 'msh_user', 'MSH-Login')
    if has('supervisor'):
        values['supervisor'] = v.login(data, 'supervisor', 'SPV (Login)')
    return values


def _merged(trainee, values, name):
    return values[name] if name in values else getattr(trainee, name, None)


def _check_consistency(trainee, values):
    start, end = _merged(trainee, values, 'start_date'), _merged(trainee, values, 'expected_completion_date')
    if start and end and end < start:
        raise v.ValidationError('Das voraussichtliche Ende darf nicht vor dem Beginn liegen.',
                                'expected_completion_date')
    current_id, target_id = _merged(trainee, values, 'current_level_id'), _merged(trainee, values, 'target_level_id')
    if current_id and target_id:
        from app.extensions import db
        current, target = db.session.get(LanguageLevel, current_id), db.session.get(LanguageLevel, target_id)
        if target.sort_order < current.sort_order:
            raise v.ValidationError('Das Ziel-Sprachniveau darf nicht unter dem aktuellen Niveau liegen.',
                                    'target_level_id')


def _check_supervisor(login, trainee_login):
    """The SPV is a staff login — neither the candidate themselves nor another candidate."""
    if login is None:
        return
    if login == trainee_login or Trainee.query.filter(func.lower(Trainee.msh_user) == login).first() is not None:
        raise v.Conflict('Der SPV muss ein Mitarbeiter-Login sein, nicht der eines Kandidaten.', 'supervisor')


def _check_login_free(login, trainee_id=None):
    """A login belongs to EXACTLY one candidate and then has no team role."""
    if login is None:
        return
    other = Trainee.query.filter(func.lower(Trainee.msh_user) == login, Trainee.id != trainee_id).first()
    if other is not None:
        raise v.Conflict('Dieser MSH-Login ist bereits einem anderen Kandidaten zugeordnet.', 'msh_user')
    if UserRole.query.filter_by(username=login).first() is not None:
        raise v.Conflict('Dieser MSH-Login hat eine Team-Rolle und kann kein Kandidat sein.', 'msh_user')
    if Instructor.query.filter_by(msh_user=login).first() is not None:
        raise v.Conflict('Dieser MSH-Login gehört einem Dozenten und kann kein Kandidat sein.', 'msh_user')


def read_new(data, actor):
    """Build a new candidate from JSON (not yet in the session)."""
    values = _read(data, None)
    _check_consistency(None, values)
    _check_login_free(values['msh_user'])
    _check_supervisor(values['supervisor'], values['msh_user'])
    return Trainee(**values, created_by=actor)


def apply_changes(trainee, data, actor):
    """Validate and apply the fields that were sent; returns True if changed."""
    values = _read(data, trainee)
    _check_consistency(trainee, values)
    if 'msh_user' in values:
        _check_login_free(values['msh_user'], trainee.id)
    if 'supervisor' in values or 'msh_user' in values:
        _check_supervisor(_merged(trainee, values, 'supervisor'), _merged(trainee, values, 'msh_user'))
    changed = {k: val for k, val in values.items() if getattr(trainee, k) != val}
    for key, val in changed.items():
        setattr(trainee, key, val)
    if changed:
        trainee.updated_by = actor
    return bool(changed)

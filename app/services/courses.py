"""Kurse: anlegen/aendern mit Querpruefungen, Teilnehmer zuordnen.

Zuordnungs-Regeln (Dozent und Modul passen zum Kurs):
- das Modul gehoert zu einem Curriculum GENAU dieses Sprachniveaus und ist nicht archiviert
- der Dozent ist aktiv (nicht archiviert, Status AKTIV) und unterrichtet das Niveau
Zeitliche Konflikte (Dozent/Kandidat doppelt eingeplant) prueft die Terminplanung.
"""
from sqlalchemy import func

from app.extensions import db
from app.models.course import STATUSES, Course
from app.models.course_module import CourseModule
from app.models.course_participant import CourseParticipant
from app.models.instructor import Instructor
from app.models.language_level import LanguageLevel
from app.models.trainee import Trainee
from app.services import validation as v


def row(data, name, model, what):
    value = data.get(name)
    if value in (None, ''):
        return None
    try:
        row = db.session.get(model, int(value))
    except (TypeError, ValueError):
        row = None
    if row is None:
        raise v.ValidationError(f'Bitte einen gültigen {what} auswählen.', name)
    return row


def _check_name_free(name, course_id=None):
    other = Course.query.filter(func.lower(Course.name) == name.lower(), Course.archived_at.is_(None),
                                Course.id != course_id).first()
    if other is not None:
        raise v.Conflict('Einen Kurs mit diesem Namen gibt es bereits.', 'name')


def check_restorable(course):
    _check_name_free(course.name, course.id)


def check_module(module, level):
    if module.curriculum.level_id != level.id:
        raise v.Conflict(f'Das Modul „{module.name}“ gehört nicht zum Sprachniveau {level.name}.', 'module_id')
    if module.status == 'ARCHIVED':
        raise v.Conflict(f'Das Modul „{module.name}“ ist archiviert.', 'module_id')


def check_instructor(instructor, level):
    if instructor.is_archived or instructor.status != 'ACTIVE':
        raise v.Conflict(f'{instructor.name} ist derzeit nicht aktiv und kann nicht zugeordnet werden.',
                         'instructor_id')
    if not instructor.teaches(level.id):
        raise v.Conflict(f'{instructor.name} unterrichtet das Sprachniveau {level.name} nicht.', 'instructor_id')


def read(data, course=None):
    """Mitgeschickte Felder pruefen (beim Anlegen alle) und gegeneinander abgleichen."""
    has = (lambda key: key in data) if course else (lambda key: True)
    values = {}
    if has('name'):
        values['name'] = v.text(data, 'name', 'Name', 160, required=True)
        _check_name_free(values['name'], getattr(course, 'id', None))
    if has('description'):
        values['description'] = v.text(data, 'description', 'Beschreibung', 4000)
    if has('status'):
        status = data.get('status') or 'PLANNED'
        if status not in STATUSES:
            raise v.ValidationError('Bitte einen gültigen Status auswählen.', 'status')
        values['status'] = status

    level = course.level if course else None
    if has('level_id'):
        level = v.reference(data, 'level_id', 'Sprachniveau', LanguageLevel, getattr(course, 'level_id', None))
        if level is None:
            raise v.ValidationError('Bitte ein Sprachniveau auswählen.', 'level_id')
        values['level_id'] = level.id
    level_changed = course is None or values.get('level_id', course.level_id) != course.level_id

    # Modul/Dozent pruefen, wenn sie neu gesetzt werden ODER das Niveau wechselt.
    module = row(data, 'module_id', CourseModule, 'Modul') if has('module_id') else getattr(course, 'module', None)
    if module is not None and (has('module_id') and module.id != getattr(course, 'module_id', None)
                               or level_changed):
        check_module(module, level)
    if has('module_id'):
        values['module_id'] = module.id if module else None

    instructor = (row(data, 'instructor_id', Instructor, 'Dozenten') if has('instructor_id')
                  else getattr(course, 'instructor', None))
    if instructor is not None and (has('instructor_id') and instructor.id != getattr(course, 'instructor_id', None)
                                   or level_changed):
        check_instructor(instructor, level)
    if has('instructor_id'):
        values['instructor_id'] = instructor.id if instructor else None
    return values


def participants(course_id):
    """Teilnehmer eines Kurses (nach Name), je mit Zeitpunkt der Aufnahme."""
    return (db.session.query(Trainee, CourseParticipant.added_at)
            .join(CourseParticipant, CourseParticipant.trainee_id == Trainee.id)
            .filter(CourseParticipant.course_id == course_id)
            .order_by(func.lower(Trainee.name)).all())


def add_participants(course, raw_ids, actor):
    """Kandidaten aufnehmen; bereits enthaltene werden uebersprungen. Liefert die neu Aufgenommenen."""
    if not isinstance(raw_ids, list) or not raw_ids:
        raise v.ValidationError('Bitte mindestens einen Kandidaten auswählen.', 'trainee_ids')
    try:
        ids = {int(value) for value in raw_ids}
    except (TypeError, ValueError):
        raise v.ValidationError('Bitte gültige Kandidaten auswählen.', 'trainee_ids') from None
    trainees = Trainee.query.filter(Trainee.id.in_(ids)).all()
    if len(trainees) != len(ids) or any(t.is_archived for t in trainees):
        raise v.ValidationError('Bitte nur aktive (nicht archivierte) Kandidaten auswählen.', 'trainee_ids')
    present = {tid for (tid,) in db.session.query(CourseParticipant.trainee_id).filter_by(course_id=course.id)}
    added = [t for t in trainees if t.id not in present]
    for trainee in added:
        db.session.add(CourseParticipant(course_id=course.id, trainee_id=trainee.id, added_by=actor))
    return sorted(added, key=lambda t: t.name.lower())


def participant_counts(course_ids):
    if not course_ids:
        return {}
    rows = (db.session.query(CourseParticipant.course_id, func.count(CourseParticipant.trainee_id))
            .filter(CourseParticipant.course_id.in_(course_ids)).group_by(CourseParticipant.course_id))
    return dict(rows.all())


def courses_of_trainees(trainee_ids):
    """Je Kandidat: seine nicht archivierten Kurse (id, name, Dozent) — eine Query."""
    if not trainee_ids:
        return {}
    rows = (db.session.query(CourseParticipant.trainee_id, Course)
            .join(Course, Course.id == CourseParticipant.course_id)
            .filter(CourseParticipant.trainee_id.in_(trainee_ids), Course.archived_at.is_(None))
            .order_by(Course.name))
    result = {}
    for tid, course in rows:
        result.setdefault(tid, []).append({'id': course.id, 'name': course.name, 'status': course.status,
                                           'instructor': course.instructor.ref() if course.instructor else None})
    return result

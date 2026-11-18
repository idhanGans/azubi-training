"""Dozenten anlegen/aendern: Feld-Pruefung, Niveaus, Wochen-Verfuegbarkeit, Login."""
import re

from sqlalchemy import func

from app.extensions import db
from app.models.course import Course
from app.models.instructor import STATUSES, Instructor
from app.models.language_level import LanguageLevel
from app.models.trainee import Trainee
from app.services import validation as v

_TIME = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
WEEKDAYS = ('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')


def _levels(data, instructor):
    raw = data.get('level_ids')
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise v.ValidationError('Bitte die Sprachniveaus als Liste angeben.', 'level_ids')
    current = {level.id for level in instructor.levels} if instructor else set()
    levels = {}
    for value in raw:
        try:
            level = db.session.get(LanguageLevel, int(value))
        except (TypeError, ValueError):
            level = None
        # ein deaktiviertes Niveau darf bleiben, aber nicht neu gewaehlt werden
        if level is None or (not level.active and level.id not in current):
            raise v.ValidationError('Bitte gültige Sprachniveaus auswählen.', 'level_ids')
        levels[level.id] = level
    return sorted(levels.values(), key=lambda level: level.sort_order)


def _availability(data):
    raw = data.get('availability')
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise v.ValidationError('Die Verfügbarkeit muss eine Liste sein.', 'availability')
    slots = {}
    for slot in raw:
        if not isinstance(slot, dict) or slot.get('weekday') not in range(7):
            raise v.ValidationError('Bitte einen gültigen Wochentag angeben.', 'availability')
        day, start, end = slot['weekday'], slot.get('start'), slot.get('end')
        label = WEEKDAYS[day]
        if not (isinstance(start, str) and _TIME.match(start) and isinstance(end, str) and _TIME.match(end)):
            raise v.ValidationError(f'{label}: Bitte Beginn und Ende als Uhrzeit (HH:MM) angeben.', 'availability')
        if end <= start:
            raise v.ValidationError(f'{label}: Das Ende muss nach dem Beginn liegen.', 'availability')
        if day in slots:
            raise v.ValidationError(f'{label}: Bitte je Wochentag nur ein Zeitfenster angeben.', 'availability')
        slots[day] = {'weekday': day, 'start': start, 'end': end}
    return [slots[day] for day in sorted(slots)]


def _check_login_free(login, instructor_id=None):
    """Ein Login gehoert hoechstens EINEM Dozenten und nie einem Kandidaten."""
    if login is None:
        return
    if Trainee.query.filter(func.lower(Trainee.msh_user) == login).first() is not None:
        raise v.Conflict('Dieser MSH-Login gehört einem Kandidaten und kann kein Dozent sein.', 'msh_user')
    other = Instructor.query.filter(Instructor.msh_user == login, Instructor.id != instructor_id).first()
    if other is not None:
        raise v.Conflict(f'Dieser MSH-Login ist bereits dem Dozenten {other.name} zugeordnet.', 'msh_user')


def read(data, instructor=None):
    """Mitgeschickte Felder pruefen (beim Anlegen alle). Liefert (Werte, Niveaus|None)."""
    has = (lambda key: key in data) if instructor else (lambda key: True)
    values = {}
    if has('name'):
        values['name'] = v.text(data, 'name', 'Name', 200, required=True)
    if has('email'):
        values['email'] = v.email(data, 'email', 'E-Mail')
    if has('msh_user'):
        values['msh_user'] = v.login(data, 'msh_user', 'MSH-Login')
        _check_login_free(values['msh_user'], getattr(instructor, 'id', None))
    if has('qualification'):
        values['qualification'] = v.text(data, 'qualification', 'Qualifikation', 2000)
    if has('specialization'):
        values['specialization'] = v.text(data, 'specialization', 'Spezialisierung', 200)
    if has('availability'):
        values['availability'] = _availability(data)
    if has('status'):
        status = data.get('status') or 'ACTIVE'
        if status not in STATUSES:
            raise v.ValidationError('Bitte einen gültigen Status auswählen.', 'status')
        values['status'] = status
    levels = _levels(data, instructor) if has('level_ids') else None
    return values, levels


def open_courses(instructor_id):
    """Nicht archivierte, nicht abgeschlossene Kurse des Dozenten."""
    return (Course.query.filter(Course.instructor_id == instructor_id, Course.archived_at.is_(None),
                                Course.status != 'COMPLETED').order_by(Course.name).all())


def check_archivable(instructor):
    courses = open_courses(instructor.id)
    if courses:
        names = ', '.join(c.name for c in courses[:3]) + (' …' if len(courses) > 3 else '')
        raise v.Conflict(f'Der Dozent ist noch laufenden oder geplanten Kursen zugeordnet: {names}. '
                         'Bitte zuerst einen anderen Dozenten zuordnen.')


def course_counts(instructor_ids):
    """Je Dozent: Anzahl nicht archivierter Kurse (eine Query)."""
    if not instructor_ids:
        return {}
    rows = (db.session.query(Course.instructor_id, func.count(Course.id))
            .filter(Course.instructor_id.in_(instructor_ids), Course.archived_at.is_(None))
            .group_by(Course.instructor_id))
    return dict(rows.all())

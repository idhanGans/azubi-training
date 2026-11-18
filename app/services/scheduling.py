"""Scheduling (Terminplanung): validate input, prevent time conflicts, availability.

Conflict rules (apply to non-cancelled sessions of non-archived courses):
- Instructor: at most one session at the same time
- Candidate: at most one session at the same time — a session's participants
  are those of its course, so the check runs over all of the candidate's courses
Two sessions overlap if one starts before the other ends
(directly adjoining is NOT a conflict).

Every write scheduling action runs under `lock()`: this way two simultaneous
requests can never both see "free" and double-book.
"""
import re
from datetime import date, timedelta

from sqlalchemy import func, or_, text

from app.extensions import db
from app.models.course import Course
from app.models.course_module import CourseModule
from app.models.course_participant import CourseParticipant
from app.models.course_session import STATUSES, CourseSession
from app.models.instructor import Instructor
from app.models.trainee import Trainee
from app.services import courses as course_svc, validation as v
from app.services.local_time import de_day, local_parts, to_utc, today

_HHMM = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
MAX_MINUTES = 10 * 60
MAX_REPEAT = 52
INSTRUCTOR_CONFLICT = 'Zeitkonflikt erkannt. Der Dozent ist zu diesem Zeitpunkt bereits eingeplant.'


def hours(sessions):
    """Teaching time in hours (2 decimal places) — "Mein Unterricht" (my teaching) and the instructor report."""
    return round(sum(s.duration_minutes for s in sessions) / 60, 2)


def lock():
    """Transaction lock for scheduling (ends with commit/rollback)."""
    db.session.execute(text("SELECT pg_advisory_xact_lock(hashtext('azubi-training.scheduling'))"))


def _hhmm(data, name, label):
    value = data.get(name)
    if not isinstance(value, str) or not _HHMM.match(value):
        raise v.ValidationError(f'Bitte für „{label}“ eine Uhrzeit (HH:MM) angeben.', name)
    return value


def _window(day, start, end):
    if end <= start:
        raise v.ValidationError('Die Endzeit muss nach der Startzeit liegen.', 'end')
    starts, ends = to_utc(day, start), to_utc(day, end)
    if (ends - starts).total_seconds() > MAX_MINUTES * 60:
        raise v.ValidationError('Ein Termin darf höchstens 10 Stunden dauern.', 'end')
    return starts, ends


def _day(data):
    now = today()
    day = v.day(data, 'date', 'Datum', earliest=now - timedelta(days=366), latest=now + timedelta(days=2 * 366))
    if day is None:
        raise v.ValidationError('Bitte ein Datum angeben.', 'date')
    return day


def _details(data, session):
    has = (lambda key: key in data) if session else (lambda key: True)
    values = {}
    for name, label, max_len in (('room', 'Raum', 80), ('location', 'Ort', 200)):
        if has(name):
            values[name] = v.text(data, name, label, max_len)
    if has('online_url'):
        values['online_url'] = v.url(data, 'online_url', 'Online-Link')
    if has('notes'):
        values['notes'] = v.text(data, 'notes', 'Notizen', 4000)
    return values


def _assignments(data, course, session):
    """Module and instructor: when creating, default from the course, otherwise only if sent.

    What gets checked is what is being NEWLY assigned (an instructor who has since
    become inactive on an existing session therefore does not block changing the room).
    """
    values = {}
    if session is None or 'module_id' in data:
        module = course_svc.row(data, 'module_id', CourseModule, 'Modul') if 'module_id' in data else course.module
        if module is not None and 'module_id' in data and module.id != getattr(session, 'module_id', None):
            course_svc.check_module(module, course.level)
        values['module_id'] = module.id if module else None
    if session is None or 'instructor_id' in data:
        instructor = (course_svc.row(data, 'instructor_id', Instructor, 'Dozenten') if 'instructor_id' in data
                      else course.instructor)
        if instructor is not None and instructor.id != getattr(session, 'instructor_id', None):
            course_svc.check_instructor(instructor, course.level)
        values['instructor_id'] = instructor.id if instructor else None
    return values


def read_new(data, course):
    """New sessions (with `repeat_until` weekly up to and including this date)."""
    if course.is_archived:
        raise v.ValidationError('Für einen archivierten Kurs können keine Termine angelegt werden.', 'course_id')
    day, start, end = _day(data), _hhmm(data, 'start', 'Beginn'), _hhmm(data, 'end', 'Ende')
    _window(day, start, end)
    days = [day]
    until = v.day(data, 'repeat_until', 'Wiederholen bis')
    if until is not None:
        if until < day:
            raise v.ValidationError('„Wiederholen bis“ darf nicht vor dem Datum liegen.', 'repeat_until')
        days = [day + timedelta(weeks=i) for i in range((until - day).days // 7 + 1)]
        if len(days) > MAX_REPEAT:
            raise v.ValidationError(f'Höchstens {MAX_REPEAT} Termine auf einmal anlegen.', 'repeat_until')
    shared = {**_details(data, None), **_assignments(data, course, None)}
    return [dict(shared, course_id=course.id, starts_at=starts, ends_at=ends)
            for starts, ends in (_window(d, start, end) for d in days)]


def read_changes(data, session):
    """Validate the sent fields of an existing session (moving, instructor, module, cancelling ...)."""
    values = {**_details(data, session), **_assignments(data, session.course, session)}
    if {'date', 'start', 'end'} & set(data):
        day, start = local_parts(session.starts_at)
        _, end = local_parts(session.ends_at)
        day = _day(data) if 'date' in data else date.fromisoformat(day)
        start = _hhmm(data, 'start', 'Beginn') if 'start' in data else start
        end = _hhmm(data, 'end', 'Ende') if 'end' in data else end
        values['starts_at'], values['ends_at'] = _window(day, start, end)
    if 'status' in data:
        status = data.get('status')
        if status not in STATUSES:
            raise v.ValidationError('Bitte einen gültigen Status auswählen.', 'status')
        values['status'] = status
        if status == 'CANCELLED':
            values['cancel_reason'] = v.text(data, 'cancel_reason', 'Grund der Absage', 500, required=True)
        else:
            values['cancel_reason'] = None
    return values


def _describe(session):
    day, start = local_parts(session.starts_at)
    _, end = local_parts(session.ends_at)
    return {'session_id': session.id, 'course': session.course.name,
            'date': day, 'start': start, 'end': end,
            'text': f'{session.course.name}, {de_day(day)}, {start}–{end} Uhr'}


def _overlapping(windows):
    return or_(*((CourseSession.starts_at < ends) & (CourseSession.ends_at > starts) for starts, ends in windows))


def _active():
    return (CourseSession.status != 'CANCELLED') & Course.archived_at.is_(None)


def check_conflicts(windows, instructor_id, trainee_ids, exclude_ids=(), exclude_course_id=None):
    """Raises Conflict (409, with `details`) if the instructor or candidates are already scheduled.

    `windows`: list of (start, end) in UTC. The session's own entries (`exclude_ids`)
    do not count; nor do those of a course (`exclude_course_id`) — when adding new
    participants the course is checked against the OTHER courses.
    """
    if not windows:
        return
    base = (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
            .filter(_active(), _overlapping(windows)))
    if exclude_ids:
        base = base.filter(CourseSession.id.notin_(list(exclude_ids)))
    if exclude_course_id is not None:
        base = base.filter(CourseSession.course_id != exclude_course_id)
    if instructor_id is not None:
        taken = base.filter(CourseSession.instructor_id == instructor_id).order_by(CourseSession.starts_at).all()
        if taken:
            first = _describe(taken[0])
            raise v.Conflict(f'{INSTRUCTOR_CONFLICT} ({first["text"]})', 'instructor_id',
                             details={'kind': 'instructor', 'sessions': [_describe(s) for s in taken[:10]]})
    if trainee_ids:
        rows = (base.join(CourseParticipant, CourseParticipant.course_id == CourseSession.course_id)
                .join(Trainee, Trainee.id == CourseParticipant.trainee_id)
                .filter(CourseParticipant.trainee_id.in_(list(trainee_ids)))
                .with_entities(Trainee.id, Trainee.name, CourseSession)
                .order_by(func.lower(Trainee.name), CourseSession.starts_at).all())
        if rows:
            names = list(dict.fromkeys(name for _, name, _ in rows))
            first = _describe(rows[0][2])
            who = (f'{names[0]} ist' if len(names) == 1
                   else 'Folgende Kandidaten sind' if len(names) <= 5 else f'{len(names)} Kandidaten sind')
            listed = f': {", ".join(names)}' if 1 < len(names) <= 5 else ''
            raise v.Conflict(f'Zeitkonflikt erkannt. {who} zu diesem Zeitpunkt bereits eingeplant{listed} '
                             f'({first["text"]}).', 'trainee_ids',
                             details={'kind': 'candidate', 'candidates': [
                                 {'trainee_id': tid, 'name': name, **_describe(s)} for tid, name, s in rows[:20]]})


def participant_ids(course_id):
    return [tid for (tid,) in db.session.query(CourseParticipant.trainee_id).filter_by(course_id=course_id)]


def future_windows(course_id):
    """Upcoming, non-cancelled sessions of a course (for new participants)."""
    rows = (CourseSession.query.filter(CourseSession.course_id == course_id, CourseSession.status != 'CANCELLED',
                                       CourseSession.ends_at > func.now()))
    return [(s.starts_at, s.ends_at) for s in rows]


def availability_warnings(instructor, windows):
    """Hints (not an error) when sessions fall outside the weekly availability."""
    if instructor is None or not instructor.availability:
        return []
    slots = {slot['weekday']: slot for slot in instructor.availability}
    outside = []
    for starts, ends in windows:
        day, start = local_parts(starts)
        _, end = local_parts(ends)
        slot = slots.get(date.fromisoformat(day).weekday())
        if slot is None or start < slot['start'] or end > slot['end']:
            outside.append(de_day(day) + f' {start}–{end} Uhr')
    if not outside:
        return []
    more = f' und {len(outside) - 3} weitere' if len(outside) > 3 else ''
    return [f'Außerhalb der Verfügbarkeit von {instructor.name}: {", ".join(outside[:3])}{more}.']

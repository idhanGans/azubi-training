"""Attendance (Anwesenheit): recording/correcting and the attendance rate — in EXACTLY this one place.

Rate (`rate`) = (Present + Late) / (Present + Late + Absent).
- "Excused" counts neither as present nor as an absence (it falls out of the
  denominator), but is reported separately.
- Only RECORDED entries of non-cancelled sessions count; a session without
  a record is not an absence.
- Without any countable entries the rate is `None` (displayed as "-"), not 0 %.
Whoever wants to change the rule changes `ATTENDED`/`COUNTED` — nothing else.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select

from app.extensions import db
from app.models.attendance import STATUSES, Attendance
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import ATTENDANCE_LEAD, CourseSession
from app.models.trainee import Trainee
from app.services import validation as v
from app.services.local_time import TZ_NAME

ATTENDED = ('PRESENT', 'LATE')
COUNTED = ('PRESENT', 'LATE', 'ABSENT')
LABELS = {'PRESENT': 'Anwesend', 'LATE': 'Verspätet', 'EXCUSED': 'Entschuldigt', 'ABSENT': 'Abwesend'}

_EMPTY = {'present': 0, 'late': 0, 'excused': 0, 'absent': 0, 'recorded': 0, 'rate': None}


def rate(attended, counted):
    return round(attended / counted, 4) if counted else None


def _counted(query):
    """Only entries of non-cancelled sessions of non-archived courses."""
    return (query.join(CourseSession, CourseSession.id == Attendance.session_id)
            .join(Course, Course.id == CourseSession.course_id)
            .filter(CourseSession.status != 'CANCELLED', Course.archived_at.is_(None)))


def stats(trainee_ids, course_condition=None, period=None):
    """Per candidate: count per status + rate (one GROUP BY query).

    `course_condition` (from `scope.course_condition`) restricts to visible
    courses — an instructor only sees the rate over THEIR OWN courses. `period` =
    (start, end) in UTC restricts to sessions within this period.
    """
    if not trainee_ids:
        return {}
    rows = stats_by(Attendance.trainee_id, trainee_ids, course_condition, period)
    return {tid: {k: v for k, v in row.items() if k != 'minutes_late'} for tid, row in rows.items()}


def stats_by(key, trainee_ids=None, course_condition=None, period=None):
    """Like `stats`, but grouped by `key` (e.g. `Course.id`) and with the sum of late minutes."""
    a = Attendance
    q = db.session.query(key, *(func.sum(case((a.status == s, 1), else_=0)) for s in STATUSES),
                         func.coalesce(func.sum(a.minutes_late), 0))
    q = _counted(q)
    if trainee_ids is not None:
        q = q.filter(a.trainee_id.in_(list(trainee_ids)))
    if course_condition is not None:
        q = q.filter(course_condition)
    if period is not None:
        q = q.filter(CourseSession.starts_at >= period[0], CourseSession.starts_at < period[1])
    result = {}
    for group, present, late, excused, absent, minutes in q.group_by(key):
        present, late, excused, absent = int(present), int(late), int(excused), int(absent)
        result[group] = {'present': present, 'late': late, 'excused': excused, 'absent': absent,
                         'recorded': present + late + excused + absent,
                         'rate': rate(present + late, present + late + absent), 'minutes_late': int(minutes)}
    return result


def pooled(per_trainee):
    """Overall rate across several candidates: all countable entries combined (not the average of the rates)."""
    total = {k: sum(s[k] for s in per_trainee.values()) for k in ('present', 'late', 'excused', 'absent', 'recorded')}
    return {**total, 'rate': rate(total['present'] + total['late'], total['present'] + total['late'] + total['absent'])}


def stats_for(trainee_id, course_condition=None):
    return stats([trainee_id], course_condition).get(trainee_id, dict(_EMPTY))


def weekly(trainee_id, course_condition=None):
    """Per calendar week (Monday, local time): count per status + rate — same rule as `stats`."""
    a = Attendance
    week = func.date_trunc('week', func.timezone(TZ_NAME, CourseSession.starts_at)).label('week')
    q = db.session.query(week, *(func.sum(case((a.status == s, 1), else_=0)) for s in STATUSES))
    q = _counted(q).filter(a.trainee_id == trainee_id)
    if course_condition is not None:
        q = q.filter(course_condition)
    result = []
    for start, present, late, excused, absent in q.group_by(week).order_by(week):
        present, late, excused, absent = int(present), int(late), int(excused), int(absent)
        result.append({'week_start': start.date().isoformat(), 'present': present, 'late': late,
                       'excused': excused, 'absent': absent,
                       'rate': rate(present + late, present + late + absent)})
    return result


def recent(trainee_id, course_condition=None, limit=10):
    """Most recent entries of a candidate with its session (newest first)."""
    q = _counted(db.session.query(Attendance, CourseSession)).filter(Attendance.trainee_id == trainee_id)
    if course_condition is not None:
        q = q.filter(course_condition)
    return q.order_by(CourseSession.starts_at.desc()).limit(limit).all()


def sheet(session):
    """Recording list of a session: course participants + who already has an entry (including those removed later)."""
    records = {r.trainee_id: r for r in Attendance.query.filter_by(session_id=session.id)}
    members = {tid for (tid,) in db.session.query(CourseParticipant.trainee_id).filter_by(course_id=session.course_id)}
    trainees = Trainee.query.filter(Trainee.id.in_(members | set(records))).order_by(func.lower(Trainee.name)).all()
    return [{'trainee': {'id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, 'nickname': t.nickname,
                         'archived': t.is_archived, 'in_course': t.id in members},
             'attendance': records[t.id].to_dict() if t.id in records else None} for t in trainees]


#: Open attendance = sessions of the last this many days without complete entries.
OPEN_ATTENDANCE_DAYS = 14


def lock(session):
    """Row lock on the session until commit: two simultaneous recordings run one after another —
    otherwise both would create the same entry and the second would fail on the UNIQUE rule (500)."""
    db.session.execute(select(CourseSession.id).where(CourseSession.id == session.id).with_for_update())
    db.session.refresh(session)              # state after waiting (e.g. cancelled in the meantime)


def check_recordable(session):
    if session.status == 'CANCELLED':
        raise v.Conflict('Für einen abgesagten Termin kann keine Anwesenheit erfasst werden.', 'session')
    if session.starts_at - ATTENDANCE_LEAD > datetime.now(timezone.utc):
        raise v.Conflict('Die Anwesenheit kann erst ab Beginn des Termins erfasst werden.', 'session')
    if session.course.is_archived:
        raise v.Conflict('Der Kurs ist archiviert.', 'session')


def recordable(session):
    """{trainee_id: name} — who may be recorded or corrected for this session: current course
    participants AND former ones (with an entry at any session of this course, e.g. after a group
    change), each not archived. Former ones are optional: nobody has to send them along."""
    current = select(CourseParticipant.trainee_id).where(CourseParticipant.course_id == session.course_id)
    former = (select(Attendance.trainee_id).join(CourseSession, CourseSession.id == Attendance.session_id)
              .where(CourseSession.course_id == session.course_id))
    return dict(db.session.query(Trainee.id, Trainee.name)
                .filter(Trainee.archived_at.is_(None), or_(Trainee.id.in_(current), Trainee.id.in_(former))))


def _entry(raw, members):
    if not isinstance(raw, dict):
        raise v.ValidationError('Ungültiger Eintrag.', 'entries')
    try:
        tid = int(raw.get('trainee_id'))
    except (TypeError, ValueError):
        raise v.ValidationError('Ungültiger Kandidat.', 'entries') from None
    if tid not in members:
        raise v.ValidationError('Anwesenheit nur für Teilnehmer dieses Kurses.', 'entries')
    status = raw.get('status')
    if status not in STATUSES:
        raise v.ValidationError('Bitte für jeden Kandidaten einen gültigen Status wählen.', 'entries')
    try:
        minutes = v.integer(raw, 'minutes_late', 'Minuten zu spät', 1, 600) if status == 'LATE' else None
        note = v.text(raw, 'note', 'Notiz', 500)
    except v.ValidationError as err:     # the field is the entries list, not the single row
        raise v.ValidationError(err.message, 'entries') from None
    return tid, {'status': status, 'minutes_late': minutes, 'note': note}


def record(session, entries, actor):
    """Create or correct entries. Returns {trainee_name: [old, new]} for the activity log.

    Current and former course participants (`recordable`) can be recorded —
    whoever changed group stays correctable in the old sessions.
    """
    if not isinstance(entries, list) or not entries:
        raise v.ValidationError('Bitte mindestens einen Eintrag senden.', 'entries')
    members = recordable(session)
    parsed = dict(_entry(raw, members) for raw in entries)
    if len(parsed) != len(entries):
        raise v.ValidationError('Jeder Kandidat darf nur einmal vorkommen.', 'entries')
    existing = {r.trainee_id: r for r in Attendance.query.filter(Attendance.session_id == session.id,
                                                                  Attendance.trainee_id.in_(list(parsed)))}
    names = members
    changes = {}
    for tid, values in parsed.items():
        row = existing.get(tid)
        if row is None:
            db.session.add(Attendance(session_id=session.id, trainee_id=tid, recorded_by=actor, **values))
            changes[names[tid]] = [None, _label(values)]
        elif any(getattr(row, k) != val for k, val in values.items()):
            changes[names[tid]] = [_label(row.to_dict()), _label(values)]
            for key, val in values.items():
                setattr(row, key, val)
            row.updated_by = actor
    return changes


def _label(values):
    text = LABELS[values['status']]
    if values.get('minutes_late'):
        text += f' ({values["minutes_late"]} Min.)'
    return text


def open_sessions(instructor_id=None, days=OPEN_ATTENDANCE_DAYS, course_condition=None):
    """Past sessions (last `days` days) that are still missing entries — of one instructor
    (`instructor_id`) and/or within the scope (`course_condition`)."""
    now = datetime.now(timezone.utc)
    window = (CourseSession.starts_at <= now, CourseSession.starts_at > now - timedelta(days=days))
    recorded = (db.session.query(Attendance.session_id, func.count(Attendance.id).label('n'))
                .join(CourseSession, CourseSession.id == Attendance.session_id).filter(*window)
                .group_by(Attendance.session_id).subquery())
    members = (db.session.query(CourseParticipant.course_id, func.count(CourseParticipant.trainee_id).label('n'))
               .group_by(CourseParticipant.course_id).subquery())
    q = (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
         .join(members, members.c.course_id == CourseSession.course_id)
         .outerjoin(recorded, recorded.c.session_id == CourseSession.id)
         .filter(CourseSession.status != 'CANCELLED', Course.archived_at.is_(None), *window,
                 func.coalesce(recorded.c.n, 0) < members.c.n))
    if instructor_id is not None:
        q = q.filter(CourseSession.instructor_id == instructor_id)
    if course_condition is not None:
        q = q.filter(course_condition)
    return q.order_by(CourseSession.starts_at.desc(), CourseSession.id.desc()).all()

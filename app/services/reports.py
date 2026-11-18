"""Reports: attendance, performance, instructors, candidate report — for a period.

Every tabular report returns `{'period', 'summary', 'tables': [{'id', 'title', 'columns', 'rows'}]}`;
the UI and the CSV export (`services/csv_export.py`) render every table the same way.
Nothing is recalculated here: rates from `attendance`, results from `scoring`/stored
ratings, skills and modules from `progress`. Scope via `scope`.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import lazyload

from app.extensions import db
from app.models.assessment import FEEDBACK_FIELDS, Assessment
from app.models.assessment_category import SKILLS
from app.models.assessment_score import AssessmentScore
from app.models.attendance import Attendance
from app.models.course import STATUS_LABELS as COURSE_STATUS_LABELS, Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.instructor import Instructor
from app.models.trainee import Trainee
from app.services import attendance, progress, scheduling, scope, scoring
from app.services.courses import courses_of_trainees
from app.services.local_time import day_range_utc, local_parts


@dataclass
class Filters:
    first: date
    last: date
    course_id: int = None
    level_id: int = None

    @property
    def utc(self):
        return day_range_utc(self.first, self.last)

    def as_dict(self):
        return {'from': self.first.isoformat(), 'to': self.last.isoformat(),
                'course_id': self.course_id, 'level_id': self.level_id}


def col(key, label, kind='text'):
    return {'key': key, 'label': label, 'type': kind}


def _condition(identity, filters):
    """Course condition = scope AND, if applicable, the chosen course."""
    condition = scope.course_condition(identity)
    if filters.course_id:
        chosen = Course.id == filters.course_id
        condition = chosen if condition is None else condition & chosen
    return condition


def _trainees(identity, filters):
    q = Trainee.query.filter(Trainee.archived_at.is_(None))
    visible = scope.trainee_ids(identity)
    if visible is not None:
        q = q.filter(Trainee.id.in_(visible))
    if filters.course_id:
        q = q.filter(Trainee.id.in_(db.select(CourseParticipant.trainee_id)
                                    .where(CourseParticipant.course_id == filters.course_id)))
    if filters.level_id:
        q = q.filter(Trainee.current_level_id == filters.level_id)
    return q.order_by(func.lower(Trainee.name)).all()


def _person(t):
    return {'candidate_id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, 'abteilung': t.abteilung,
            'level': t.current_level.code if t.current_level else None}


# ---------- Attendance ----------

def attendance_report(identity, filters):
    trainees = _trainees(identity, filters)
    condition = _condition(identity, filters)
    ids = [t.id for t in trainees]
    per = attendance.stats_by(Attendance.trainee_id, ids, condition, filters.utc) if ids else {}
    courses = courses_of_trainees([t.id for t in trainees])
    rows = []
    for t in trainees:
        s = per.get(t.id)
        rows.append({**_person(t), 'courses': [c['name'] for c in courses.get(t.id, [])],
                     **(s or {'present': 0, 'late': 0, 'excused': 0, 'absent': 0, 'recorded': 0, 'rate': None,
                              'minutes_late': 0})})
    by_course = attendance.stats_by(Course.id, [t.id for t in trainees], condition, filters.utc) if trainees else {}
    held = _held_sessions(list(by_course), filters)
    course_rows = []
    for course in Course.query.filter(Course.id.in_(list(by_course))).order_by(func.lower(Course.name)):
        course_rows.append({'course': course.name, 'instructor': course.instructor.name if course.instructor else None,
                            'sessions': held.get(course.id, 0), **by_course[course.id]})
    counts = [('present', 'Anwesend', 'int'), ('late', 'Verspätet', 'int'), ('excused', 'Entschuldigt', 'int'),
              ('absent', 'Abwesend', 'int'), ('rate', 'Quote', 'rate'), ('minutes_late', 'Min. zu spät', 'int')]
    total = attendance.pooled(per) if per else None
    return {'period': filters.as_dict(),
            'summary': {'candidates': len(trainees), 'with_entries': len(per), 'attendance': total,
                        'absences': total['absent'] if total else 0, 'late': total['late'] if total else 0},
            'tables': [
                {'id': 'candidates', 'title': 'Anwesenheit je Kandidat',
                 'columns': [col('candidate_no', 'Nr.'), col('name', 'Name', 'candidate'), col('abteilung', 'Abteilung'),
                             col('courses', 'Kurse')] + [col(k, label, kind) for k, label, kind in counts],
                 'rows': rows},
                {'id': 'courses', 'title': 'Anwesenheit je Kurs',
                 'columns': [col('course', 'Kurs'), col('instructor', 'Dozent'), col('sessions', 'Termine', 'int')]
                 + [col(k, label, kind) for k, label, kind in counts],
                 'rows': course_rows}]}


def _held_sessions(course_ids, filters):
    """{course_id: number of held (non-cancelled, started) sessions within the period} — one query."""
    if not course_ids:
        return {}
    start, end = filters.utc
    now = datetime.now(timezone.utc)
    return dict(db.session.query(CourseSession.course_id, func.count(CourseSession.id))
                .filter(CourseSession.course_id.in_(course_ids), CourseSession.status != 'CANCELLED',
                        CourseSession.starts_at >= start, CourseSession.starts_at < end, CourseSession.starts_at <= now)
                .group_by(CourseSession.course_id))


# ---------- Performance (Academic) ----------

def _final_in_period(trainee_ids, filters, slim=False):
    """Completed ratings within the period. `slim`: only with the template (evaluation across many
    ratings) — candidate, instructor, course and points are left out, points then via
    `AssessmentScore.points_of`."""
    if not trainee_ids:
        return []
    q = Assessment.query.filter(Assessment.trainee_id.in_(trainee_ids), Assessment.status == 'FINAL',
                                Assessment.assessed_on >= filters.first, Assessment.assessed_on <= filters.last)
    if filters.course_id:
        q = q.filter(Assessment.course_id == filters.course_id)
    if slim:
        q = q.options(lazyload(Assessment.trainee), lazyload(Assessment.instructor), lazyload(Assessment.course),
                      lazyload(Assessment.scores))
    return q.order_by(Assessment.assessed_on, Assessment.id).all()


def _avg(values):
    return round(sum(values) / len(values), 1) if values else None


def academic_report(identity, filters):
    trainees = _trainees(identity, filters)
    ids = [t.id for t in trainees]
    finals = _final_in_period(ids, filters, slim=True)
    points = AssessmentScore.points_of([a.id for a in finals])
    by_template, skill_values, latest, counts = defaultdict(list), defaultdict(list), {}, defaultdict(int)
    for a in finals:
        by_template[a.template.name].append(a)
        latest[a.trainee_id] = a
        counts[a.trainee_id] += 1
        values = progress.skill_values(a.template, scoring.evaluate(a.template, points[a.id]))
        for skill, value in values.items():
            skill_values[skill].append(value)
    template_rows = [{'template': name, 'assessments': len(rows), 'candidates': len({a.trainee_id for a in rows}),
                      'avg': _avg([float(a.overall_percent) for a in rows]),
                      'pass_rate': round(sum(1 for a in rows if a.passed) / len(rows), 4)}
                     for name, rows in sorted(by_template.items())]
    skill_rows = [{'skill': SKILLS[code], 'assessments': len(skill_values[code]), 'avg': _avg(skill_values[code]),
                   'min': min(skill_values[code]), 'max': max(skill_values[code])}
                  for code in SKILLS if skill_values.get(code)]
    person_rows = []
    for t in trainees:
        a = latest.get(t.id)
        person_rows.append({**_person(t), 'assessments': counts.get(t.id, 0),
                            'latest_template': a.template.name if a else None,
                            'latest_date': a.assessed_on.isoformat() if a else None,
                            'latest': float(a.overall_percent) if a else None, 'passed': a.passed if a else None})
    module_rows = []
    condition = _condition(identity, filters)
    cq = Course.query.filter(Course.archived_at.is_(None), Course.module_id.isnot(None))
    if condition is not None:
        cq = cq.filter(condition)
    if filters.level_id:
        cq = cq.filter(Course.level_id == filters.level_id)
    participants = dict(db.session.query(CourseParticipant.course_id, func.count(CourseParticipant.trainee_id))
                        .group_by(CourseParticipant.course_id))
    courses = cq.order_by(func.lower(Course.name)).all()
    catalog = progress.curriculum_modules({c.module.curriculum_id for c in courses})
    for course in courses:
        done = progress.course_completion(course, catalog[course.module.curriculum_id])
        module_rows.append({'course': course.name, 'status': COURSE_STATUS_LABELS[course.status], 'participants': participants.get(course.id, 0),
                            'current': done['current']['name'] if done['current'] else None,
                            'completed': done['completed'], 'total': done['total'], 'percent': done['percent']})
    return {'period': filters.as_dict(),
            'summary': {'candidates': len(trainees), 'assessments': len(finals),
                        'avg_latest': _avg([float(a.overall_percent) for a in latest.values()]),
                        'pass_rate': round(sum(1 for a in finals if a.passed) / len(finals), 4) if finals else None},
            'tables': [
                {'id': 'templates', 'title': 'Durchschnitt je Bewertungsvorlage',
                 'columns': [col('template', 'Vorlage'), col('assessments', 'Bewertungen', 'int'),
                             col('candidates', 'Kandidaten', 'int'), col('avg', 'Ø Ergebnis (%)', 'percent'),
                             col('pass_rate', 'Bestanden', 'rate')],
                 'rows': template_rows},
                {'id': 'skills', 'title': 'Fertigkeiten',
                 'columns': [col('skill', 'Fertigkeit'), col('assessments', 'Bewertungen', 'int'),
                             col('avg', 'Ø (%)', 'percent'), col('min', 'Min. (%)', 'percent'),
                             col('max', 'Max. (%)', 'percent')],
                 'rows': skill_rows},
                {'id': 'candidates', 'title': 'Ergebnis je Kandidat (neueste Bewertung im Zeitraum)',
                 'columns': [col('candidate_no', 'Nr.'), col('name', 'Name', 'candidate'), col('level', 'Niveau'),
                             col('assessments', 'Bewertungen', 'int'), col('latest_template', 'Vorlage'),
                             col('latest_date', 'Datum', 'date'), col('latest', 'Ergebnis (%)', 'percent'),
                             col('passed', 'Bestanden', 'bool')],
                 'rows': person_rows},
                {'id': 'modules', 'title': 'Module je Kurs',
                 'columns': [col('course', 'Kurs'), col('status', 'Status'), col('participants', 'Teilnehmer', 'int'),
                             col('current', 'Aktuelles Modul'), col('completed', 'Abgeschlossen', 'int'),
                             col('total', 'Module gesamt', 'int'), col('percent', 'Fortschritt (%)', 'percent')],
                 'rows': module_rows}]}


# ---------- Instructors ----------

def instructor_report(identity, filters):
    start, end = filters.utc
    now = datetime.now(timezone.utc)
    q = Instructor.query.filter(Instructor.archived_at.is_(None))
    if identity.instructor_id is not None and not scope.sees_all(identity):
        q = q.filter(Instructor.id == identity.instructor_id)
    instructors = q.order_by(func.lower(Instructor.name)).all()
    ids = [i.id for i in instructors]
    own = {i.id: (Course.query.options(lazyload('*')).filter(scope.own_courses(i.id))
                  .order_by(func.lower(Course.name)).all())
           for i in instructors}
    # candidates per course (not archived) — per instructor the union over their courses
    members = defaultdict(set)
    course_ids = {c.id for courses in own.values() for c in courses}
    if course_ids:
        for course_id, tid in (db.session.query(CourseParticipant.course_id, CourseParticipant.trainee_id)
                               .join(Trainee, Trainee.id == CourseParticipant.trainee_id)
                               .filter(CourseParticipant.course_id.in_(course_ids), Trainee.archived_at.is_(None))):
            members[course_id].add(tid)
    sessions = defaultdict(list)
    for s in (CourseSession.query.options(lazyload('*'))
              .filter(CourseSession.instructor_id.in_(ids), CourseSession.status != 'CANCELLED',
                      CourseSession.starts_at >= start, CourseSession.starts_at < end)):
        sessions[s.instructor_id].append(s)
    finals = dict(db.session.query(Assessment.instructor_id, func.count(Assessment.id))
                  .filter(Assessment.instructor_id.in_(ids), Assessment.status == 'FINAL',
                          Assessment.assessed_on >= filters.first, Assessment.assessed_on <= filters.last)
                  .group_by(Assessment.instructor_id))
    drafts = dict(db.session.query(Assessment.instructor_id, func.count(Assessment.id))
                  .filter(Assessment.instructor_id.in_(ids), Assessment.status == 'DRAFT')
                  .group_by(Assessment.instructor_id))
    open_attendance = Counter(s.instructor_id for s in attendance.open_sessions())
    rows = []
    for inst in instructors:
        courses = own[inst.id]
        held = [s for s in sessions[inst.id] if s.starts_at <= now]
        rows.append({'instructor': inst.name, 'status': inst.status,
                     'courses': len(courses), 'running': sum(1 for c in courses if c.status == 'RUNNING'),
                     'course_names': [c.name for c in courses],
                     'sessions_held': len(held), 'hours_held': scheduling.hours(held),
                     'hours_planned': scheduling.hours([s for s in sessions[inst.id] if s.starts_at > now]),
                     'candidates': len(set().union(*(members[c.id] for c in courses))),
                     'assessments_final': finals.get(inst.id, 0), 'assessments_open': drafts.get(inst.id, 0),
                     'attendance_open': open_attendance[inst.id]})
    return {'period': filters.as_dict(),
            'summary': {'instructors': len(rows), 'hours_held': round(sum(r['hours_held'] for r in rows), 2),
                        'assessments_final': sum(r['assessments_final'] for r in rows),
                        'assessments_open': sum(r['assessments_open'] for r in rows)},
            'tables': [{'id': 'instructors', 'title': 'Dozenten',
                        'columns': [col('instructor', 'Dozent'), col('courses', 'Kurse', 'int'),
                                    col('running', 'davon laufend', 'int'), col('course_names', 'Kursnamen'),
                                    col('sessions_held', 'Termine gehalten', 'int'),
                                    col('hours_held', 'Stunden gehalten', 'hours'),
                                    col('hours_planned', 'Stunden geplant', 'hours'),
                                    col('candidates', 'Kandidaten', 'int'),
                                    col('assessments_final', 'Bewertungen abgeschlossen', 'int'),
                                    col('assessments_open', 'Bewertungen offen', 'int'),
                                    col('attendance_open', 'Anwesenheit offen', 'int')],
                        'rows': rows}]}


# ---------- Candidate report ----------

def first_activity(trainee_id):
    """Earliest rating date and earliest session with attendance (local time) — start of the entire activity log."""
    first_assessment = db.session.query(func.min(Assessment.assessed_on)).filter_by(trainee_id=trainee_id).scalar()
    first_session = (db.session.query(func.min(CourseSession.starts_at))
                     .join(Attendance, Attendance.session_id == CourseSession.id)
                     .filter(Attendance.trainee_id == trainee_id).scalar())
    return first_assessment, date.fromisoformat(local_parts(first_session)[0]) if first_session else None


def candidate_report(identity, trainee, filters):
    """One candidate: master data, level, ratings + feedback, progress, attendance.

    Without internal notes — the report may be passed on to the candidate.
    """
    condition = scope.course_condition(identity)
    finals = _final_in_period([trainee.id], Filters(filters.first, filters.last))
    history = []
    for a in finals:
        result = scoring.evaluate(a.template, a.points())
        history.append({**a.public_dict(), 'categories': [{k: c[k] for k in ('name', 'score', 'max_score', 'percent',
                                                                            'passed')} for c in result['categories']]})
    return {'period': filters.as_dict(),
            'candidate': {**trainee.public_dict(), 'courses': courses_of_trainees([trainee.id]).get(trainee.id, [])},
            'assessments': history,
            'feedback': [{'date': a['assessed_on'], 'template': a['template']['name'],
                          **{f: a[f] for f in FEEDBACK_FIELDS if a[f]}} for a in history
                         if any(a[f] for f in FEEDBACK_FIELDS)],
            'progress': {**{k: v for k, v in progress.assessments(trainee.id).items() if k == 'skills'},
                         'modules': progress.modules(trainee.id, condition)},
            'attendance': {'period': attendance.stats(
                [trainee.id], condition, filters.utc).get(trainee.id), 'total': attendance.stats_for(trainee.id, condition)}}

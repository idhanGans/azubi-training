"""Team dashboard: metrics and action items (Handlungsbedarf) — THE ONE place for their definitions.

Everything within the scope (`scope`): instructors only see their own courses and their
participants, all other roles see all non-archived candidates.

Metrics:
- Candidates: non-archived candidates.
- Active candidates: of those, in at least one running (RUNNING), non-archived course.
- Average rating: mean of the LATEST completed rating per candidate (whoever is rated
  often does not count multiple times).
- Average attendance: rate over all countable entries combined
  (rule from `services/attendance.py`).
- Modules completed: sum of completed / sum of all modules (rule from
  `services/progress.py`), over all candidates with a course module.
- Open ratings: drafts.
- Module rating: open = past module sessions without stars for the attendees (`lesson_ratings.open_sessions`);
  coaching (Begleitung) = latest module rating at level D (guideline: D -> bimbingan).
Action items only appear if the role is also allowed to act on them.
"""
from collections import Counter

from sqlalchemy import func

from app.extensions import db
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.trainee import Trainee
from app.services import attendance, lesson_ratings, lesson_scoring, progress, scope, scoring

#: Below this attendance rate a candidate appears under "action items" (Handlungsbedarf).
LOW_ATTENDANCE = 0.8
#: This many names per list — the rest is shown as a count.
LIST_LIMIT = 8


def _ref(t, **extra):
    return {'id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, **extra}


def overview(identity):
    condition = scope.course_condition(identity)
    visible = scope.trainee_ids(identity)
    q = Trainee.query.filter(Trainee.archived_at.is_(None))
    if visible is not None:
        q = q.filter(Trainee.id.in_(visible))
    trainees = q.order_by(func.lower(Trainee.name)).all()
    ids = [t.id for t in trainees]

    course_q = (db.session.query(CourseParticipant.trainee_id, Course.status)
                .join(Course, Course.id == CourseParticipant.course_id)
                .filter(CourseParticipant.trainee_id.in_(ids), Course.archived_at.is_(None)))
    if condition is not None:
        course_q = course_q.filter(condition)
    in_course, running = set(), set()
    for tid, status in course_q:
        in_course.add(tid)
        if status == 'RUNNING':
            running.add(tid)

    # latest completed rating per candidate — only the number, not full records
    latest = dict(db.session.query(Assessment.trainee_id, Assessment.overall_percent)
                  .filter(Assessment.trainee_id.in_(ids), Assessment.status == 'FINAL')
                  .distinct(Assessment.trainee_id)
                  .order_by(Assessment.trainee_id, Assessment.assessed_on.desc(), Assessment.id.desc()))
    latest = {tid: float(value) for tid, value in latest.items()}
    drafts = Assessment.query.filter(Assessment.trainee_id.in_(ids), Assessment.status == 'DRAFT').count()

    att = attendance.stats(ids, condition)
    completed = total = 0
    for entries in progress.modules_of(in_course, condition).values():
        for entry in entries:
            completed, total = completed + entry['completed'], total + entry['total']

    kpis = {
        'candidates': len(ids),
        'active_candidates': len(running),
        'avg_assessment': round(sum(latest.values()) / len(latest), 1) if latest else None,
        'assessed_candidates': len(latest),
        'attendance': attendance.pooled(att) if att else None,
        'modules_completed': scoring.percent(completed, total) if total else None,
        'modules': {'completed': completed, 'total': total},
        'open_assessments': drafts,
    }
    status_counts = Counter(t.status.name if t.status else None for t in trainees)
    level_counts = Counter(t.current_level.code if t.current_level else None for t in trainees)
    level_order = {t.current_level.code: t.current_level.sort_order for t in trainees if t.current_level}
    body = {
        'scope': 'all' if condition is None else 'own_courses',
        'kpis': kpis,
        'by_status': [{'label': k, 'count': v} for k, v in status_counts.most_common()],
        'by_level': [{'label': k, 'count': v} for k, v in
                     sorted(level_counts.items(), key=lambda kv: (kv[0] is None, level_order.get(kv[0], 0)))],
        'attention': _attention(identity, trainees, in_course, att, drafts, condition),
    }
    return body


def _listing(rows):
    return {'count': len(rows), 'items': rows[:LIST_LIMIT]}


def _attention(identity, trainees, in_course, att, drafts, condition):
    """Action items (Handlungsbedarf) — only items that this role itself can act on."""
    items = {}
    if identity.can('assessment.edit'):
        items['open_assessments'] = {'count': drafts}
    if identity.can('attendance.manage'):
        sessions = attendance.open_sessions(course_condition=condition)
        items['open_attendance'] = {'count': len(sessions), 'days': attendance.OPEN_ATTENDANCE_DAYS,
                                    'items': [s.public_dict() for s in sessions[:LIST_LIMIT]]}
    if identity.can('attendance.view'):
        low = [_ref(t, rate=att[t.id]['rate']) for t in trainees
               if t.id in att and att[t.id]['rate'] is not None and att[t.id]['rate'] < LOW_ATTENDANCE]
        items['low_attendance'] = {**_listing(sorted(low, key=lambda r: r['rate'])),
                                   'below_percent': round(LOW_ATTENDANCE * 100)}
    if identity.can('assessment.create'):
        sessions = lesson_ratings.open_sessions(course_condition=condition)
        items['open_lesson_ratings'] = {'count': len(sessions), 'days': lesson_ratings.OPEN_DAYS,
                                        'items': sessions[:LIST_LIMIT]}
    if identity.can('assessment.view'):
        latest = lesson_ratings.latest_levels([t.id for t in trainees], condition)
        items['lesson_coaching'] = _listing([_ref(t, date=latest[t.id][1]) for t in trainees if t.id in latest
                                             and latest[t.id][0] == lesson_scoring.COACHING_LEVEL])
    if identity.can('schedule.edit'):
        items['without_course'] = _listing([_ref(t) for t in trainees if t.id not in in_course])
    if identity.can('candidate.edit'):
        items['incomplete_profile'] = _listing([
            _ref(t, missing=[f for f, v in (('status', t.status_id), ('current_level', t.current_level_id),
                                           ('program', t.program_id)) if v is None])
            for t in trainees if t.status_id is None or t.current_level_id is None or t.program_id is None])
    return items

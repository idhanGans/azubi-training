"""Overall rating (Gesamtbewertung) per trainee (meeting topic "Azubi 2027") — THE ONE place that computes
parts, total and rank.

Total = Report 10 % + German 40 % + SPV 30 % + Intern 20 %; each part on a 0-100 scale.
- Report: from the daily self-reports in the period — hours (6 h of work per workday; more than 8 h on
  one day does not count), regularity (workdays with a report / workdays) and detail level (text per
  day, full from 400 characters). Workdays = Mon-Fri from the start (the very first report ever, or the
  candidate's start date, or "from") to yesterday (or "to").
- German: module ratings per the Panduan guideline (avg points out of 20, only ratings with a total —
  one per module of a session) and attendance in the German course (rate).
- SPV: ratings by SPV and leader (avg of the three categories 1-10), Intern: by the internal team — each
  first averaged per program month, then over the rated months (every month counts equally).
If a part is missing, it is "Pending" (never 0); the total is formed from the parts that ARE present
(weights of the missing parts factored out), so a rank already exists before the rating is complete —
only without any rated part does it stay open. Equal points = equal rank; each department has its own
rank. Always computed over ALL active candidates, shown only what the viewer may see
(`supervision.visible_condition`).
Whoever changes the rule changes the constants here — the UI reads them via `rules()`.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import Date, case, cast, func, literal
from sqlalchemy.orm import lazyload, selectinload

from app.extensions import db
from app.models.course import Course
from app.models.course_session import CourseSession
from app.models.department import Department
from app.models.lesson_rating import LessonRating
from app.models.staff_rating import CATEGORIES, StaffRating
from app.models.trainee import Trainee
from app.models.training_report import TrainingReport
from app.services import attendance, lesson_scoring, local_time, rating_board, supervision, training_stats
from app.services.rating_board import SCALE

#: Weight per part in percent (sum 100) — order = display order.
WEIGHTS = {'report': 10, 'german': 40, 'spv': 30, 'intern': 20}
SCORE_MAX = 100

HOURS_PER_WORKDAY = 6           # work hours per workday (plus 2 h German course = 8 h per day)
DAY_HOURS_CAP = 8               # more hours on one day do not count
DETAIL_FULL_CHARS = 400         # from this many characters of text a day counts as reported in detail
REPORT_PARTS = {'hours': 50, 'regularity': 25, 'detail': 25}      # shares of the report part (sum 100)
GERMAN_PARTS = {'lessons': 75, 'attendance': 25}                  # shares of the German part (sum 100)
WORKDAYS = range(1, 6)          # ISO weekdays Mon-Fri

_ISO_DAY = r'^\d{4}-\d{2}-\d{2}$'


def rules():
    """Rule numbers for the UI and downloads — nothing is recalculated there. `parts` = order of the
    parts (JSON sorts the keys of `weights`)."""
    return {'parts': list(WEIGHTS), 'weights': WEIGHTS, 'score_max': SCORE_MAX, 'hours_per_workday': HOURS_PER_WORKDAY,
            'day_hours_cap': DAY_HOURS_CAP, 'detail_full_chars': DETAIL_FULL_CHARS, 'report_parts': REPORT_PARTS,
            'german_parts': GERMAN_PARTS, 'german_max': lesson_scoring.TOTAL_MAX, 'rating_scale': list(SCALE),
            'categories': list(CATEGORIES)}


def _r(value, digits=1):
    return None if value is None else round(value, digits)


def workdays(first, last):
    """Number of workdays (Mon-Fri) from `first` to `last` inclusive."""
    if first is None or last is None or last < first:
        return 0
    days = (last - first).days + 1
    full, rest = divmod(days, 7)
    return full * 5 + sum(1 for i in range(rest) if (first + timedelta(days=i)).isoweekday() in WORKDAYS)


# ---------- Part "Report" ----------

def _report_window(first, last):
    """Start/end for the report part: without "from" starting at the very first report ever, without
    "to" until yesterday."""
    end = last or local_time.today() - timedelta(days=1)
    start = first
    if start is None:
        earliest = (db.session.query(func.min(TrainingReport.period))
                    .filter(TrainingReport.period.op('~')(_ISO_DAY)).scalar())
        start = date.fromisoformat(earliest) if earliest else None
    return start, end


def _report_days(start, end):
    """Per candidate: hours (capped per day), workdays with a report, avg detail level — one query."""
    r = TrainingReport
    day = (db.session.query(
        r.trainee_id.label('tid'), r.period.label('period'),
        func.least(func.coalesce(func.sum(r.hours), 0), DAY_HOURS_CAP).label('hours'),
        func.least(func.sum(func.coalesce(func.length(r.learned), 0)) / literal(float(DETAIL_FULL_CHARS)), 1)
        .label('detail'))
        .join(Trainee, Trainee.id == r.trainee_id)
        .filter(r.period.op('~')(_ISO_DAY), r.period >= start.isoformat(), r.period <= end.isoformat(),
                r.period >= func.coalesce(func.to_char(Trainee.start_date, 'YYYY-MM-DD'), start.isoformat()))
        .group_by(r.trainee_id, r.period).subquery())
    weekday = func.extract('isodow', cast(day.c.period, Date))
    q = db.session.query(day.c.tid, func.sum(day.c.hours),
                         func.count().filter(weekday.between(WORKDAYS.start, WORKDAYS.stop - 1)),
                         func.avg(day.c.detail)).group_by(day.c.tid)
    return {tid: (float(hours or 0), int(days), float(detail or 0)) for tid, hours, days, detail in q}


def _report_part(trainee, start, end, days):
    begin = max(start, trainee.start_date) if trainee.start_date and start else start
    due = workdays(begin, end)
    if not due:
        return {'score': None, 'workdays': 0}
    hours, reported, detail = days.get(trainee.id, (0.0, 0, 0.0))
    target = due * HOURS_PER_WORKDAY
    parts = {'hours': min(hours / target, 1), 'regularity': min(reported / due, 1), 'detail': detail}
    score = sum(REPORT_PARTS[k] * parts[k] for k in REPORT_PARTS) * SCORE_MAX / 100
    return {'score': _r(score), 'workdays': due, 'days_reported': reported, 'hours': _r(hours),
            'target_hours': target, 'from': begin.isoformat(), 'to': end.isoformat(),
            **{f'{k}_percent': _r(v * 100) for k, v in parts.items()}}


# ---------- Part "German" ----------

def _lessons(ids, period):
    """Per candidate the module ratings (result via `lesson_scoring`) — one query."""
    q = (db.session.query(LessonRating, CourseSession.starts_at)
         .options(lazyload('*'))
         .join(CourseSession, CourseSession.id == LessonRating.session_id)
         .join(Course, Course.id == CourseSession.course_id)
         .filter(CourseSession.status != 'CANCELLED', Course.archived_at.is_(None)))
    if ids is not None:
        q = q.filter(LessonRating.trainee_id.in_(ids))
    if period is not None:
        q = q.filter(CourseSession.starts_at >= period[0], CourseSession.starts_at < period[1])
    result = defaultdict(list)
    for rating, starts_at in q.order_by(CourseSession.starts_at, LessonRating.id):
        result[rating.trainee_id].append(lesson_scoring.evaluate(rating.values()))
    return result


def _german_part(results, stats):
    att = {k: stats.get(k, 0) for k in ('present', 'late', 'excused', 'absent')}
    att['rate'] = stats.get('rate')
    results = [x for x in results if x['complete']]           # ratings with gaps have no total
    if not results or att['rate'] is None:
        return {'score': None, 'count': len(results), 'attendance': att}
    average = sum(x['total'] for x in results) / len(results)
    lessons = average / lesson_scoring.TOTAL_MAX
    score = (GERMAN_PARTS['lessons'] * lessons + GERMAN_PARTS['attendance'] * att['rate']) * SCORE_MAX / 100
    return {'score': _r(score), 'count': len(results), 'average_total': _r(average),
            'lessons_percent': _r(lessons * 100), 'attendance': att,
            'latest_level': results[-1]['level'], 'levels': dict(Counter(x['level'] for x in results))}


# ---------- Parts "SPV" and "Intern" ----------

def _rating_part(group):
    if not group['count']:
        return {'score': None, 'count': 0, 'months': {}}
    months = {m: {'count': x['count'], 'mean': x['mean'], 'score': _r(x['mean'] / SCALE[1] * SCORE_MAX),
                  **{c: x[c] for c in CATEGORIES}} for m, x in group['months'].items()}
    return {'score': _r(group['mean'] / SCALE[1] * SCORE_MAX), 'count': group['count'], 'mean': group['mean'],
            **{c: group[c] for c in CATEGORIES}, 'months': months}


# ---------- Total + Rank ----------

def _total(parts):
    """Total from the parts that ARE PRESENT (weights of the missing parts factored out), so a rank
    already exists before the rating is complete. Only without any rated part does it stay open."""
    present = [k for k in WEIGHTS if parts[k]['score'] is not None]
    missing = [k for k in WEIGHTS if parts[k]['score'] is None]
    if not present:
        return None, missing
    weight = sum(WEIGHTS[k] for k in present)
    return _r(sum(WEIGHTS[k] * parts[k]['score'] for k in present) / weight), missing


def _rank(rows, key):
    """Competition rank (1, 1, 3 ...) by total, only rows that have a total."""
    ranked = sorted((r for r in rows if r['total'] is not None), key=lambda r: -r['total'])
    previous, place = None, 0
    for index, row in enumerate(ranked, start=1):
        if row['total'] != previous:
            place, previous = index, row['total']
        row[key] = place


def _compute(first, last, month=None):
    """All active candidates with parts, total and rank (overall + per department) — fixed number of queries.
    `month`: SPV/Intern only from the ratings of that program month (instead of by submission date)."""
    trainees = (Trainee.query.options(lazyload('*')).filter(Trainee.archived_at.is_(None))
                .order_by(func.lower(Trainee.name)).all())
    departments = {d.id: d for d in Department.query.options(selectinload(Department.leaders))}
    period = local_time.day_range_utc(first, last) if first and last else None
    start, end = _report_window(first, last)
    days = _report_days(start, end) if start else {}
    lessons = _lessons(None, period)
    att = attendance.stats([t.id for t in trainees], period=period)
    ratings = training_stats.rating_stats(period=None if month else period, month=month)
    rows = []
    for t in trainees:
        r = ratings.get(t.id, training_stats.RATING_EMPTY)
        parts = {'report': _report_part(t, start, end, days) if start else {'score': None, 'workdays': 0},
                 'german': _german_part(lessons.get(t.id, []), att.get(t.id, {})),
                 'spv': _rating_part(r['spv']), 'intern': _rating_part(r['intern'])}
        total, missing = _total(parts)
        department = departments.get(t.department_id)
        rows.append({'id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, 'nickname': t.nickname,
                     'abteilung': t.abteilung, 'department': department.ref() if department else None,
                     'supervisor': t.supervisor, 'leaders': [x.username for x in department.leaders] if department
                     else [], 'parts': parts, 'total': total, 'missing': missing, 'rank': None,
                     'department_rank': None})
    _rank(rows, 'rank')
    by_department = defaultdict(list)
    for row in rows:
        by_department[(row['department'] or {}).get('id')].append(row)
    for group in by_department.values():
        _rank(group, 'department_rank')
    rows.sort(key=lambda r: (r['total'] is None, -(r['total'] or 0), r['name'].lower()))
    return rows


_NOTE_GROUP = {'SPV': 'spv', 'LEITER': 'spv', 'INTERN': 'intern'}      # same as training_stats._GROUP_OF


def _attach_rating_notes(rows, identity, first, last):
    """Attach rater notes (`StaffRating.note`) per trainee to the SPV/Intern parts — same view as in the
    trainee report: ALL notes only for the team (`assessment.view`, then with the rater), otherwise only own."""
    for row in rows:
        row['parts']['spv']['notes'] = []
        row['parts']['intern']['notes'] = []
    ids = [r['id'] for r in rows]
    if not ids:
        return
    team = identity.can('assessment.view')
    q = StaffRating.query.filter(StaffRating.trainee_id.in_(ids), StaffRating.note.isnot(None))
    if not team:
        q = q.filter(StaffRating.rater == identity.username)
    if first and last:
        period = local_time.day_range_utc(first, last)
        q = q.filter(StaffRating.created_at >= period[0], StaffRating.created_at < period[1])
    by_part = defaultdict(list)
    for r in q.order_by(StaffRating.month.desc(), StaffRating.created_at.desc()):
        if not (r.note or '').strip():
            continue
        by_part[(r.trainee_id, _NOTE_GROUP[r.kind])].append(
            {'rater': r.rater if team else None, 'kind': r.kind, 'month': r.month, 'note': r.note,
             'created_at': r.created_at.isoformat() if r.created_at else None})
    rows_by_id = {r['id']: r for r in rows}
    for (tid, part), notes in by_part.items():
        rows_by_id[tid]['parts'][part]['notes'] = notes


def _visible_ids(identity):
    condition = supervision.visible_condition(identity)
    if condition is None:
        return None
    return {i for (i,) in db.session.query(Trainee.id).filter(condition, Trainee.archived_at.is_(None))}


def overview(identity, department_id=None, first=None, last=None):
    """Leaderboard for the viewer: everyone (report.view) or their own assigned candidates.
    Only whoever sees everyone sees the overall rank; otherwise only the rank within the department."""
    visible = _visible_ids(identity)
    rows = [r for r in _compute(first, last) if visible is None or r['id'] in visible]
    departments = sorted({(r['department']['id'], r['department']['name']) for r in rows if r['department']},
                         key=lambda d: d[1].lower())
    if department_id is not None:
        rows = [r for r in rows if (r['department'] or {}).get('id') == department_id]
    if visible is not None:
        for row in rows:
            row['rank'] = None
    _attach_rating_notes(rows, identity, first, last)
    return {'rules': rules(), 'period': {'from': first.isoformat() if first else None,
                                         'to': last.isoformat() if last else None},
            'departments': [{'id': i, 'name': n} for i, n in departments], 'department_id': department_id,
            'overall_rank': visible is None, 'rows': rows}


def detail(identity, trainee, first=None, last=None):
    """Report for ONE candidate: parts with derivation, total, rank, groups and the ratings — other
    people's ratings (rater + note) only for the team (`assessment.view`), otherwise only own."""
    rows = _compute(first, last)
    row = next(r for r in rows if r['id'] == trainee.id)
    if not identity.can('report.view'):
        row['rank'] = None
    team = identity.can('assessment.view')
    q = StaffRating.query.filter_by(trainee_id=trainee.id)
    if not team:
        q = q.filter_by(rater=identity.username)
    if first and last:
        period = local_time.day_range_utc(first, last)
        q = q.filter(StaffRating.created_at >= period[0], StaffRating.created_at < period[1])
    ratings = [r.to_dict() for r in q.order_by(StaffRating.month.desc(), StaffRating.created_at.desc())]
    return {**row, 'rules': rules(), 'period': {'from': first.isoformat() if first else None,
                                                'to': last.isoformat() if last else None},
            'groups': rating_board.groups_of(trainee.id), 'ratings': ratings, 'all_ratings': team,
            'overall_rank': identity.can('report.view')}

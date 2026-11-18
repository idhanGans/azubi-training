"""Rating by SPV, leader and internal team: overview + recording (`rating.view`/`rating.create`).

Which candidates someone sees and as what they rate is decided by `supervision.py` (SPV: their candidates,
leader: their departments, internal team: all active ones). Shown are name, nickname, department, position,
running groups and the metrics of the part the viewer contributes to (SPV feedback or Intern): count and
average of all raters, their OWN ratings in full. No contact data, no reports, no notes of others.

The program runs `PROGRAM_MONTHS` months; every rater gives ONE rating per candidate and month. Open for
rating are all months that have started (`MONTH_STARTS`), so a missed month can still be made up.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import lazyload

from app.extensions import db
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.department import Department
from app.models.staff_rating import CATEGORIES, StaffRating
from app.models.trainee import Trainee
from app.services import local_time, supervision, training_stats, validation as v

#: Scale of every category — the UI reads it from the API.
SCALE = (1, 10)
NOTE_MAX = 1000
#: First day of each program month (program start = first daily report, 17.09.2026).
MONTH_STARTS = (date(2026, 9, 17), date(2026, 10, 17), date(2026, 11, 17))
PROGRAM_MONTHS = len(MONTH_STARTS)
_LABELS = {'r_practical': 'Praktische Leistung', 'r_reliability': 'Zuverlässigkeit',
           'r_motivation': 'Motivation & Verhalten'}


def current_month(today=None):
    """Program month running today (1..PROGRAM_MONTHS; before the start 1, after the end the last)."""
    today = today or local_time.today()
    return max([1] + [n for n, start in enumerate(MONTH_STARTS, start=1) if start <= today])


def _month_end(n):
    """Last day of program month `n` (the day before the next start; the last month runs one calendar month)."""
    if n < PROGRAM_MONTHS:
        return MONTH_STARTS[n] - timedelta(days=1)
    start = MONTH_STARTS[-1]
    return start.replace(year=start.year + start.month // 12, month=start.month % 12 + 1) - timedelta(days=1)


def months_info():
    """Month rules for the UI: current month, selectable months, total months, dates of every month."""
    now = current_month()
    return {'month': now, 'months': list(range(1, now + 1)), 'program_months': PROGRAM_MONTHS,
            'calendar': [{'month': n, 'from': start.isoformat(), 'to': _month_end(n).isoformat(), 'started': n <= now}
                         for n, start in enumerate(MONTH_STARTS, start=1)]}


def groups_of(trainee_id):
    """Running groups of a candidate."""
    return _groups([trainee_id]).get(trainee_id, [])


def _groups(trainee_ids=None):
    """Running/planned, non-archived courses per candidate (one query)."""
    q = (select(CourseParticipant.trainee_id, Course.name)
         .join(Course, Course.id == CourseParticipant.course_id)
         .where(Course.archived_at.is_(None), Course.status != 'COMPLETED')
         .order_by(Course.name))
    if trainee_ids is not None:
        q = q.where(CourseParticipant.trainee_id.in_(trainee_ids))
    groups = {}
    for tid, name in db.session.execute(q):
        groups.setdefault(tid, []).append(name)
    return groups


def _part(kind):
    return 'intern' if kind == supervision.INTERN else 'spv'


def _own(login, trainee_ids=None):
    """{trainee_id: {month: own rating}} of `login` (one query) — with "correctable"."""
    q = StaffRating.query.filter_by(rater=login)
    if trainee_ids is not None:
        q = q.filter(StaffRating.trainee_id.in_(trainee_ids))
    own = {}
    for r in q:
        own.setdefault(r.trainee_id, {})[r.month] = {**r.to_dict(), 'editable': r.is_editable_by(login)}
    return own


def _row(trainee, kind, groups, stats, department, own):
    s = stats.get(trainee.id, training_stats.RATING_EMPTY)
    part = _part(kind)
    return {'id': trainee.id, 'name': trainee.name, 'nickname': trainee.nickname, 'abteilung': trainee.abteilung,
            'department': department.ref() if department else None,
            'groups': groups.get(trainee.id, []), 'kind': kind, 'part': part, 'stats': s[part],
            'rating_mine': s['rating_mine'], 'months_mine': s['months_mine'], 'mine': own.get(trainee.id, {})}


def board(identity):
    """All candidates `identity` may rate — with the kind (SPV/LEITER/INTERN) per candidate."""
    q = Trainee.query.options(lazyload('*')).filter(Trainee.archived_at.is_(None))
    condition = supervision.rateable_condition(identity)
    if condition is not None:
        q = q.filter(condition)
    trainees = q.order_by(Trainee.name).all()
    departments = {d.id: d for d in Department.query}
    led = supervision.leads(identity.username)
    groups, stats = _groups(), training_stats.rating_stats(rater=identity.username)
    own = _own(identity.username)
    rows = [_row(t, supervision.kind_for(identity, t, led), groups, stats, departments.get(t.department_id), own)
            for t in trainees]
    return {'trainees': rows, 'scale': list(SCALE), 'categories': list(CATEGORIES),
            'internal': identity.can('rating.internal'), **months_info()}


def rateable(identity, trainee_id):
    """(candidate, kind) — None if `identity` may not rate them (also archived/unknown)."""
    trainee = db.session.get(Trainee, trainee_id) if isinstance(trainee_id, int) else None
    kind = supervision.kind_for(identity, trainee)
    return (trainee, kind) if kind else None


def detail(identity, trainee, kind):
    """One candidate: metrics of the own part + the OWN ratings (with "correctable")."""
    login = identity.username
    stats = training_stats.rating_stats([trainee.id], rater=login)
    mine = (StaffRating.query.filter_by(trainee_id=trainee.id, rater=login)
            .order_by(StaffRating.month.desc(), StaffRating.created_at.desc()).all())
    own = _own(login, [trainee.id])
    return {'trainee': _row(trainee, kind, _groups([trainee.id]), stats, trainee.department, own),
            'scale': list(SCALE),
            'categories': list(CATEGORIES), **months_info(),
            'mine': [{**r.to_dict(), 'editable': r.is_editable_by(login)} for r in mine]}


def read_month(data, trainee, rater):
    """Month of a new rating: `month` (default the current one) — only started months, and only once per
    candidate and rater (409, then correct the existing one instead)."""
    now = current_month()
    month = v.integer(data, 'month', 'Monat', 1, PROGRAM_MONTHS)
    month = now if month is None else month
    if month > now:
        raise v.ValidationError(f'Monat {month} hat noch nicht begonnen.', 'month')
    if StaffRating.query.filter_by(trainee_id=trainee.id, rater=rater, month=month).count():
        raise v.Conflict(f'Sie haben {trainee.name} für Monat {month} schon bewertet.', 'month')
    return month


def read_scores(data):
    """Check the inputs of a rating (create and correct) — all three categories are required."""
    low, high = SCALE
    values = {key: v.integer(data, key, label, low, high) for key, label in _LABELS.items()}
    for key, label in _LABELS.items():
        if values[key] is None:
            raise v.ValidationError(f'Bitte „{label}" bewerten ({low}–{high}).', key)
        values[key] = int(values[key])
    values['note'] = v.text(data, 'note', 'Notiz', NOTE_MAX)
    return values


def summary_text(values):
    """"Praxis 8 · Zuverlässigkeit 7 · Motivation 9" for the activity log."""
    return ' · '.join(f'{_LABELS[k]} {values[k]}' for k in CATEGORIES)

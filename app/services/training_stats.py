"""Metrics per participant for the team overview.

Aggregated in the database (GROUP BY) instead of loading all reports into
memory — stays a few small queries even with thousands of reports.
"""
from sqlalchemy import case, func, literal
from sqlalchemy.orm import lazyload

from app.extensions import db
from app.models.common import iso
from app.models.staff_rating import CATEGORIES, StaffRating
from app.models.trainee import Trainee
from app.models.training_report import TrainingReport


def _round(value, digits=1):
    return round(float(value), digits) if value is not None else None


def _report_stats(trainee_ids=None):
    r = TrainingReport
    q = db.session.query(
        r.trainee_id,
        func.coalesce(func.sum(r.hours), 0),
        func.count(r.id),
        func.count(func.distinct(r.period)),
        func.sum(case((r.lang.is_(True), 1), else_=0)),
        func.sum(case((r.tech.is_(True), 1), else_=0)),
        func.max(r.created_at),
    )
    if trainee_ids is not None:
        q = q.filter(r.trainee_id.in_(trainee_ids))
    rows = q.group_by(r.trainee_id)
    return {
        tid: {'hours_total': _round(hours), 'report_count': count, 'days_reported': days,
              'lang_count': int(lang or 0), 'tech_count': int(tech or 0), 'last_report': iso(last)}
        for tid, hours, count, days, lang, tech, last in rows
    }


#: Rating kinds per part of the overall rating (`supervision.SUPERVISOR_KINDS` = SPV feedback).
_GROUP_OF = {'SPV': 'spv', 'LEITER': 'spv', 'INTERN': 'intern'}
GROUP_EMPTY = {'count': 0, **dict.fromkeys(CATEGORIES), 'mean': None, 'last': None, 'months': {}}


def _avg(values):
    values = [x for x in values if x is not None]
    return sum(values) / len(values) if values else None


def rating_stats(trainee_ids=None, rater=None, period=None, month=None):
    """Ratings by SPV/leader/internal team per participant, split by part of the overall rating
    (`spv` = SPV + leader, `intern`) and by program month: per month count, average per category and `mean`
    (average of all categories, 1..10); per part the same values as the average of the MONTHS (every rated
    month counts equally), total count and latest. Plus the overall `rating_count`/`rating_last` and, with
    `rater`, their count `rating_mine` and the months they rated (`months_mine`); `period` = (start, end) in
    UTC restricts to ratings submitted within this period, `month` to ratings of that program month.
    THE ONE place for these metrics (monitoring, rating overview, overall rating) — one query."""
    g = StaffRating
    group = case(*((g.kind == kind, name) for kind, name in _GROUP_OF.items()))
    mine = func.count(g.id).filter(g.rater == rater) if rater else literal(0)
    q = db.session.query(
        g.trainee_id, group, g.month, func.count(g.id), *(func.avg(getattr(g, c)) for c in CATEGORIES),
        func.avg((g.r_practical + g.r_reliability + g.r_motivation) / literal(float(len(CATEGORIES)))),
        func.max(g.created_at), mine)
    if trainee_ids is not None:
        q = q.filter(g.trainee_id.in_(trainee_ids))
    if period is not None:
        q = q.filter(g.created_at >= period[0], g.created_at < period[1])
    if month is not None:
        q = q.filter(g.month == month)
    raw, result = {}, {}
    for tid, name, month, count, *rest in q.group_by(g.trainee_id, group, g.month).order_by(g.month):
        *avgs, mean, last, own = rest
        raw.setdefault((tid, name), {})[month] = {'count': count, **{c: a for c, a in zip(CATEGORIES, avgs)},
                                                  'mean': mean, 'last': last}
        row = result.setdefault(tid, {**RATING_EMPTY, 'spv': dict(GROUP_EMPTY), 'intern': dict(GROUP_EMPTY),
                                      'months_mine': []})
        row['rating_count'] += count
        row['rating_mine'] += int(own)
        if own and month not in row['months_mine']:
            row['months_mine'].append(month)
        row['rating_last'] = max(filter(None, (row['rating_last'], iso(last))), default=None)
    for (tid, name), months in raw.items():
        shown = {m: {'count': x['count'], **{c: _round(x[c]) for c in CATEGORIES}, 'mean': _round(x['mean'], 2),
                     'last': iso(x['last'])} for m, x in months.items()}
        result[tid][name] = {'count': sum(x['count'] for x in months.values()),
                             **{c: _round(_avg([x[c] for x in months.values()])) for c in CATEGORIES},
                             'mean': _round(_avg([x['mean'] for x in months.values()]), 2),
                             'last': iso(max(x['last'] for x in months.values())), 'months': shown}
    for row in result.values():
        row['months_mine'].sort()
    return result


RATING_EMPTY = {'rating_count': 0, 'rating_last': None, 'rating_mine': 0, 'months_mine': [], 'spv': GROUP_EMPTY,
                'intern': GROUP_EMPTY}


_EMPTY = {
    'hours_total': 0.0, 'report_count': 0, 'days_reported': 0, 'lang_count': 0,
    'tech_count': 0, 'last_report': None, **RATING_EMPTY,
}


def report_summary(trainee_id):
    """Number of reports + total hours of a candidate (profile and "Mein Trainings-Report" = my training report)."""
    stats = _report_stats([trainee_id]).get(trainee_id, _EMPTY)
    return {'report_count': stats['report_count'], 'hours_total': stats['hours_total']}


def trainee_overview(include_archived=False, visible=None):
    """All (or all active) participants, each with report and rating metrics.

    `visible`: subquery of the visible IDs (`scope.trainee_ids`), None = all.
    """
    q = Trainee.query
    if visible is not None:
        q = q.filter(Trainee.id.in_(visible))
    if not include_archived:
        q = q.filter(Trainee.archived_at.is_(None))
    reports, ratings = _report_stats(), rating_stats()
    # only the fields the monitoring shows — not the entire profile per candidate
    return [
        {'id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, 'nickname': t.nickname, 'fach': t.fach,
         'abteilung': t.abteilung, 'msh_user': t.msh_user,
         **_EMPTY, **reports.get(t.id, {}), **ratings.get(t.id, {})}
        for t in q.options(lazyload('*')).order_by(Trainee.name)
    ]

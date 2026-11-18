"""Overall rating per program month (Monatsvergleich): month history per Azubi and month-over-month comparison.

Per program month (`rating_board.MONTH_STARTS`) the four parts are computed exactly like the overall rating
(`overall._compute`), only restricted to that month: report and German course (lessons + attendance) by the dates
of the month — a running month up to yesterday —, SPV and Intern by the rating month (`staff_rating.month`, so a
rating that was made up later still counts for its month).

Comparison month A -> month B: the change is computed over the parts that are present in BOTH months
(like-for-like, the weights of the other parts factored out) — a part that is still pending in one month never
looks like a drop. Trend: change >= +TREND_BAND points = improved, <= -TREND_BAND = declined, otherwise stagnant;
without a common part = not comparable. Whoever changes the rule changes the constants here — the UI reads them.
"""
from datetime import date, timedelta

from app.services import local_time, rating_board
from app.services.overall import WEIGHTS, _compute, _r

#: Change in points (0-100 scale) from which a month counts as improved/declined; within the band = stagnant.
TREND_BAND = 2.0
IMPROVED, STAGNANT, DECLINED, OPEN = 'IMPROVED', 'STAGNANT', 'DECLINED', 'OPEN'
TRENDS = (IMPROVED, STAGNANT, DECLINED, OPEN)
#: How many Azubis the summary names as top improvers / largest declines.
TOP_N = 3


def rules():
    return {'trend_band': TREND_BAND, 'trends': list(TRENDS), 'weights': WEIGHTS, 'parts': list(WEIGHTS)}


def _window(month):
    """(first, last) day of a started program month — a running month only up to yesterday."""
    c = rating_board.months_info()['calendar'][month - 1]
    yesterday = local_time.today() - timedelta(days=1)
    return date.fromisoformat(c['from']), min(date.fromisoformat(c['to']), yesterday)


def _month_rows(months):
    """{month: {trainee_id: row}} for the given started months — one `_compute` per month (fixed queries)."""
    return {m: {r['id']: r for r in _compute(*_window(m), month=m)} for m in months}


def _month_entry(row, running):
    if row is None:
        return None
    return {'total': row['total'], 'missing': row['missing'], 'running': running,
            'parts': {k: row['parts'][k]['score'] for k in WEIGHTS}}


def compare(a, b):
    """Change from month entry `a` to `b` over the parts present in both (like-for-like)."""
    common = [k for k in WEIGHTS if a and b and a['parts'][k] is not None and b['parts'][k] is not None]
    if not common:
        return {'trend': OPEN, 'parts': [], 'from': None, 'to': None, 'delta': None, 'percent': None,
                'part_deltas': {}}
    weight = sum(WEIGHTS[k] for k in common)
    before = sum(WEIGHTS[k] * a['parts'][k] for k in common) / weight
    after = sum(WEIGHTS[k] * b['parts'][k] for k in common) / weight
    delta = after - before
    trend = IMPROVED if delta >= TREND_BAND else DECLINED if delta <= -TREND_BAND else STAGNANT
    return {'trend': trend, 'parts': common, 'from': _r(before), 'to': _r(after), 'delta': _r(delta),
            'percent': _r(delta / before * 100) if before else None,
            'part_deltas': {k: _r(b['parts'][k] - a['parts'][k]) for k in common}}


def default_pair():
    """The two most recent COMPLETED months; until two are completed: month 1 -> month 2."""
    calendar = rating_board.months_info()['calendar']
    done = [c['month'] for c in calendar if date.fromisoformat(c['to']) < local_time.today()]
    return (done[-2], done[-1]) if len(done) >= 2 else (1, 2)


def pairs():
    """Selectable comparisons: every pair of started months (earlier -> later)."""
    started = rating_board.months_info()['months']
    return [[a, b] for i, a in enumerate(started) for b in started[i + 1:]]


def _summary(rows, pair):
    comparable = [r for r in rows if r['compare']['trend'] != OPEN]
    counts = {t: sum(1 for r in rows if r['compare']['trend'] == t) for t in TRENDS}
    avg = lambda key: _r(sum(r['compare'][key] for r in comparable) / len(comparable)) if comparable else None
    by_delta = sorted(comparable, key=lambda r: r['compare']['delta'])
    pick = lambda r: {'id': r['id'], 'name': r['name'], **{k: r['compare'][k] for k in ('from', 'to', 'delta')}}
    totals = {m: [r['months'][str(m)]['total'] for r in rows
                  if r['months'].get(str(m)) and r['months'][str(m)]['total'] is not None] for m in pair}
    return {'counts': counts, 'comparable': len(comparable),
            'cohort': {'from': avg('from'), 'to': avg('to'), 'delta': avg('delta')},
            'month_average': {str(m): _r(sum(v) / len(v)) if v else None for m, v in totals.items()},
            'top_improvers': [pick(r) for r in reversed(by_delta) if r['compare']['trend'] == IMPROVED][:TOP_N],
            'top_decliners': [pick(r) for r in by_delta if r['compare']['trend'] == DECLINED][:TOP_N]}


def overview(pair, department_id=None, supervisor=None, trend=None):
    """All active Azubis with total per started month, comparison `pair` (month A, month B), overall total/rank
    and a summary (trend counts, cohort average A vs B, top improvers/declines) — for the team (`report.view`).
    The filters also apply to the summary."""
    info = rating_board.months_info()
    started, done = info['months'], _completed()
    per_month = _month_rows(started)
    rows, supervisors, departments = [], set(), {}
    for row in _compute(None, None):
        months = {str(m): _month_entry(per_month[m].get(row['id']), m not in done) for m in started}
        a, b = (months.get(str(m)) for m in pair)
        if row['supervisor']:
            supervisors.add(row['supervisor'])
        if row['department']:
            departments[row['department']['id']] = row['department']['name']
        rows.append({k: row[k] for k in ('id', 'candidate_no', 'name', 'nickname', 'abteilung', 'department',
                                         'supervisor', 'total', 'rank', 'missing')}
                    | {'months': months, 'compare': compare(a, b)})
    rows = [r for r in rows
            if (department_id is None or (r['department'] or {}).get('id') == department_id)
            and (supervisor is None or r['supervisor'] == supervisor)
            and (trend is None or r['compare']['trend'] == trend)]
    return {'rules': rules(), 'month': info['month'], 'started': started, 'calendar': info['calendar'],
            'pair': list(pair), 'pairs': pairs(), 'default_pair': list(default_pair()),
            'departments': [{'id': i, 'name': n} for i, n in sorted(departments.items(), key=lambda d: d[1].lower())],
            'supervisors': sorted(supervisors), 'summary': _summary(rows, pair), 'rows': rows}


def _completed():
    calendar = rating_board.months_info()['calendar']
    return {c['month'] for c in calendar if date.fromisoformat(c['to']) < local_time.today()}


def history(trainee):
    """Month history of ONE Azubi: per started month total, parts with derivation (SPV/Intern with categories)
    and the change between consecutive months; `latest` = newest comparable change."""
    info = rating_board.months_info()
    done = _completed()
    months = []
    for m, rows in _month_rows(info['months']).items():
        row = rows.get(trainee.id)
        months.append({'month': m, 'running': m not in done, 'total': row['total'] if row else None,
                       'missing': row['missing'] if row else list(WEIGHTS),
                       'parts': row['parts'] if row else {k: {'score': None} for k in WEIGHTS}})
    entries = {x['month']: _month_entry(x, x['running']) for x in months}
    steps = [{'from_month': a, 'to_month': a + 1, **compare(entries[a], entries[a + 1])}
             for a in info['months'][:-1]]
    latest = next((s for s in reversed(steps) if s['trend'] != OPEN), None)
    return {'rules': rules(), 'month': info['month'], 'calendar': info['calendar'], 'history': months,
            'steps': steps, 'latest': latest}

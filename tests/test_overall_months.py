"""Month comparison (Monatsvergleich): overall rating per program month, change month A -> B over the parts present in
both months, trend, summary, month history per Azubi — and who may see it.

World (tests/test_overall.py): Dimas has lessons + reports in month 1 only; ratings month 1: SPV 8, leader 6,
internal 9 — month 2: internal 1 (made on 05.10., counts for month 2 by its rating month). Fajar: leader 5 in month 1.
"""
from datetime import date

import pytest

from app.services import overall_months
from tests.test_overall import world  # noqa: F401  (fixture)


@pytest.fixture
def today(monkeypatch):
    def set_day(day):
        monkeypatch.setattr('app.services.local_time.today', lambda: date.fromisoformat(day))
    set_day('2026-11-20')                                   # month 3 running, months 1 + 2 completed
    return set_day


def _entry(**parts):
    return {'parts': {k: parts.get(k) for k in ('report', 'german', 'spv', 'intern')}}


def test_vergleich_nur_ueber_gemeinsame_teile():
    a = _entry(report=50.0, german=80.0, spv=70.0)
    b = _entry(report=60.0, spv=80.0, intern=90.0)                       # German pending, internal new
    c = overall_months.compare(a, b)
    assert (c['parts'], c['from'], c['to'], c['delta'], c['trend']) == (['report', 'spv'], 65.0, 75.0, 10.0, 'IMPROVED')
    assert (c['percent'], c['part_deltas']) == (15.4, {'report': 10.0, 'spv': 10.0})
    assert overall_months.compare(_entry(spv=70.0), _entry(spv=71.9))['trend'] == 'STAGNANT'    # within the band
    assert overall_months.compare(_entry(spv=70.0), _entry(spv=68.0))['trend'] == 'DECLINED'    # -2.0 = declined
    assert overall_months.compare(_entry(spv=70.0), _entry(german=70.0))['trend'] == 'OPEN'     # nothing in common
    assert overall_months.compare(None, _entry(spv=1.0))['trend'] == 'OPEN'


def test_standard_vergleich_die_zwei_letzten_abgeschlossenen_monate(today):
    today('2026-11-10')
    assert overall_months.default_pair() == (1, 2)          # only month 1 completed
    today('2026-11-20')
    assert overall_months.default_pair() == (1, 2)
    today('2026-12-20')
    assert overall_months.default_pair() == (2, 3)


def test_monatsvergleich(world, today):
    body = world['admin'].get('/api/overall/months').get_json()
    assert (body['pair'], body['pairs'], body['started']) == ([1, 2], [[1, 2], [1, 3], [2, 3]], [1, 2, 3])
    rows = {r['name']: r for r in body['rows']}
    dimo = rows['Dimas']
    m1, m2, m3 = (dimo['months'][m] for m in ('1', '2', '3'))
    assert (m1['parts']['spv'], m1['parts']['intern'], m2['parts']['intern']) == (70.0, 90.0, 10.0)
    assert (m2['parts']['german'], m2['parts']['spv']) == (None, None)
    assert (m1['running'], m2['running'], m3['running']) == (False, False, True)
    c = dimo['compare']
    assert (c['parts'], c['trend'], c['part_deltas']['intern']) == (['report', 'intern'], 'DECLINED', -80.0)
    assert rows['Fajar']['compare']['parts'] == ['report'] and rows['Fajar']['compare']['trend'] == 'STAGNANT'
    assert dimo['total'] == world['admin'].get(f'/api/overall/{world["dimo"]}').get_json()['total']   # whole program
    s = body['summary']
    assert s['counts'] == {'IMPROVED': 0, 'STAGNANT': 2, 'DECLINED': 1, 'OPEN': 0} and s['comparable'] == 3
    assert [x['name'] for x in s['top_decliners']] == ['Dimas'] and s['top_improvers'] == []
    only = world['admin'].get('/api/overall/months?trend=DECLINED&from_month=1&to_month=2').get_json()
    assert [r['name'] for r in only['rows']] == ['Dimas'] and only['summary']['counts']['STAGNANT'] == 0
    spv = world['admin'].get('/api/overall/months?supervisor=endah').get_json()
    assert [r['name'] for r in spv['rows']] == ['Fajar']
    dept = world['admin'].get(f'/api/overall/months?department_id={world["erk"]}').get_json()
    assert [r['name'] for r in dept['rows']] == ['Raka'] and dept['departments'][0]['name'] == 'Bad Neuenahr'


@pytest.mark.parametrize('query', ['from_month=2&to_month=1', 'from_month=1', 'to_month=3&from_month=1&x=1',
                                   'trend=BESSER', 'from_month=0&to_month=2'])
def test_ungueltige_filter(world, today, query):
    today('2026-11-10')                                     # month 3 not started yet
    res = world['admin'].get(f'/api/overall/months?{query}')
    assert res.status_code == 400 and res.get_json()['field'] in ('from_month', 'to_month', 'trend')


def test_monatsverlauf_je_azubi(world, today):
    body = world['admin'].get(f'/api/overall/{world["dimo"]}/months').get_json()
    history = body['history']
    assert [(x['month'], x['running']) for x in history] == [(1, False), (2, False), (3, True)]
    assert (history[0]['parts']['intern']['score'], history[1]['parts']['intern']['score']) == (90.0, 10.0)
    assert history[0]['parts']['spv']['r_practical'] == 7.0                 # categories of the month (8 and 6)
    assert history[2]['parts']['report']['to'] == '2026-11-19'              # running month up to yesterday
    assert [(s['from_month'], s['to_month'], s['trend']) for s in body['steps']] == [
        (1, 2, 'DECLINED'), (2, 3, 'STAGNANT')]
    assert body['latest']['to_month'] == 3


def test_wer_den_monatsvergleich_sieht(world, today):
    hanan = world['hanan']                                  # SPV of Dimas, no team role
    assert hanan.get('/api/overall/months').status_code == 403
    assert hanan.get('/overall/months', headers={'Accept': 'text/html'}).status_code == 403
    assert hanan.get(f'/api/overall/{world["dimo"]}/months').status_code == 200        # own Azubi
    assert hanan.get(f'/api/overall/{world["raka"]}/months').status_code == 404       # not assigned
    assert world['admin'].get('/overall/months', headers={'Accept': 'text/html'}).status_code == 200

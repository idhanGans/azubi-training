"""Downloads der Gesamtbewertung: Rangliste und Bericht je Azubi — fertig deutsch fuer `doc_export`.

Inhalt = genau das, was der Betrachter in der Oberflaeche sieht (gleiche Daten aus `overall.py`).
"""
from datetime import datetime

from app.services.local_time import de_day, local_parts, today

PART_LABELS = {'report': 'Report', 'german': 'Deutsch', 'spv': 'SPV', 'intern': 'Intern'}
CATEGORY_LABELS = {'r_practical': 'Praktische Leistung', 'r_reliability': 'Zuverlässigkeit',
                   'r_motivation': 'Motivation & Verhalten'}
KIND_LABELS = {'SPV': 'SPV', 'LEITER': 'Leiter', 'INTERN': 'Intern'}
PENDING = 'Ausstehend'


def _n(value):
    """Zahl im Fliesstext deutsch: 12,5 / 80 """
    return f'{value:g}'.replace('.', ',')


def _score(part):
    return PENDING if part['score'] is None else part['score']


def _period_line(period):
    if period['from']:
        return f'Zeitraum: {de_day(period["from"])} – {de_day(period["to"])}'
    return 'Zeitraum: gesamter Verlauf'


def _weights_line(rules):
    parts = ' + '.join(f'{PART_LABELS[k]} {w} %' for k, w in rules['weights'].items())
    return f'Gewichtung: {parts}; jeder Teil 0–{rules["score_max"]}. Fehlt ein Teil, bleibt das Gesamt offen.'


def overview_doc(body, department_name=None):
    rules = body['rules']
    columns = ([{'key': 'rank', 'label': 'Platz', 'type': 'int'}] if body['overall_rank'] else []) + [
        {'key': 'department_rank', 'label': 'Platz Abt.', 'type': 'int'},
        {'key': 'candidate_no', 'label': 'K-Nr.'}, {'key': 'name', 'label': 'Name'},
        {'key': 'department', 'label': 'Abteilung'}, {'key': 'abteilung', 'label': 'Stelle'},
        {'key': 'supervisor', 'label': 'SPV'},
        *({'key': k, 'label': f'{PART_LABELS[k]} {w} %', 'type': 'number'} for k, w in rules['weights'].items()),
        {'key': 'total', 'label': 'Gesamt', 'type': 'number'}]
    rows = [{**{k: r[k] for k in ('rank', 'department_rank', 'candidate_no', 'name', 'abteilung', 'supervisor')},
             'department': (r['department'] or {}).get('name'),
             **{k: _score(r['parts'][k]) for k in rules['weights']},
             'total': PENDING if r['total'] is None else r['total']} for r in body['rows']]
    meta = [_period_line(body['period']), f'Abteilung: {department_name or "alle"}', _weights_line(rules),
            f'Stand: {de_day(today())}']
    return {'title': 'Gesamtbewertung', 'meta': meta, 'landscape': True,
            'sections': [{'title': f'Rangliste ({len(rows)} Azubis)', 'columns': columns, 'rows': rows,
                          'empty': 'Keine Azubis.'}]}


def _report_pairs(p, rules):
    if p['score'] is None:
        return [('Teil Report', PENDING), ('Grund', 'Noch kein Werktag im Zeitraum.')]
    return [('Teil Report', p['score']),
            ('Zeitraum', f'{de_day(p["from"])} – {de_day(p["to"])} ({p["workdays"]} Werktage)'),
            ('Stunden', f'{_n(p["hours"])} von {p["target_hours"]} ({rules["hours_per_workday"]} h je Werktag, '
                        f'höchstens {rules["day_hours_cap"]} h am Tag) = {_n(p["hours_percent"])} %'),
            ('Regelmäßigkeit', f'{p["days_reported"]} von {p["workdays"]} Werktagen mit Report = '
                               f'{_n(p["regularity_percent"])} %'),
            ('Ausführlichkeit', f'{_n(p["detail_percent"])} % (voll ab {rules["detail_full_chars"]} Zeichen je Tag)'),
            ('Anteile', ', '.join(f'{label} {rules["report_parts"][k]} %' for k, label in
                                  (('hours', 'Stunden'), ('regularity', 'Regelmäßigkeit'),
                                   ('detail', 'Ausführlichkeit'))))]


def _german_pairs(p, rules):
    a = p['attendance']
    attendance = (f'{a["present"]} anwesend, {a["late"]} verspätet, {a["absent"]} abwesend, '
                  f'{a["excused"]} entschuldigt')
    rate = '–' if a['rate'] is None else f'{_n(round(a["rate"] * 100, 1))} %'
    if p['score'] is None:
        return [('Teil Deutsch', PENDING), ('Modul-Bewertungen', p['count']), ('Anwesenheit', attendance)]
    return [('Teil Deutsch', p['score']),
            ('Modul-Bewertungen', f'{p["count"]}, Ø {_n(p["average_total"])} von {rules["german_max"]} Punkten '
                                  f'= {_n(p["lessons_percent"])} %'),
            ('Neuestes Level', p['latest_level']),
            ('Anwesenheit', f'{attendance} – Quote {rate}'),
            ('Anteile', f'Modul-Bewertungen {rules["german_parts"]["lessons"]} %, '
                        f'Anwesenheit {rules["german_parts"]["attendance"]} %')]


def _rating_pairs(label, p):
    if p['score'] is None:
        return [(f'Teil {label}', PENDING), ('Bewertungen', 0)]
    return [(f'Teil {label}', p['score']), ('Bewertungen', p['count']),
            *((CATEGORY_LABELS[c], p[c]) for c in CATEGORY_LABELS),
            *((f'Monat {m}', f'{x["score"]} ({x["count"]} Bewertung{"en" if x["count"] != 1 else ""})')
              for m, x in sorted(p['months'].items()))]


def detail_doc(body):
    rules = body['rules']
    ranks = [('Platz in der Abteilung', body['department_rank'])]
    if body['overall_rank']:
        ranks.insert(0, ('Platz gesamt', body['rank']))
    parts = [{'part': f'{PART_LABELS[k]}', 'weight': w, 'score': _score(body['parts'][k]),
              'weighted': None if body['parts'][k]['score'] is None else round(body['parts'][k]['score'] * w / 100, 1)}
             for k, w in rules['weights'].items()]
    parts.append({'part': 'Gesamt', 'weight': 100, 'score': PENDING if body['total'] is None else body['total'],
                  'weighted': body['total']})
    rating_columns = [{'key': 'created_at', 'label': 'Datum'}, {'key': 'kind', 'label': 'Art'},
                      *([{'key': 'rater', 'label': 'Bewerter'}] if body['all_ratings'] else []),
                      *({'key': c, 'label': label, 'type': 'int'} for c, label in CATEGORY_LABELS.items()),
                      {'key': 'note', 'label': 'Notiz'}]
    ratings = [{**r, 'created_at': de_day(local_parts(datetime.fromisoformat(r['created_at']))[0]),
                'kind': KIND_LABELS[r['kind']]}
               for r in body['ratings']]
    return {'title': f'Azubi-Bericht – {body["name"]}',
            'meta': [_period_line(body['period']), _weights_line(rules), f'Stand: {de_day(today())}'],
            'sections': [
                {'title': 'Azubi', 'pairs': [
                    ('Name', body['name'] + (f' ({body["nickname"]})' if body['nickname'] else '')),
                    ('K-Nr.', body['candidate_no']), ('Abteilung', (body['department'] or {}).get('name')),
                    ('Stelle', body['abteilung']), ('SPV', body['supervisor']), ('Leiter', body['leaders']),
                    ('Gruppen', body['groups']), *ranks]},
                {'title': 'Gesamtbewertung', 'rows': parts, 'columns': [
                    {'key': 'part', 'label': 'Teil'}, {'key': 'weight', 'label': 'Gewicht %', 'type': 'int'},
                    {'key': 'score', 'label': 'Wert (0–100)', 'type': 'number'},
                    {'key': 'weighted', 'label': 'Gewichtet', 'type': 'number'}]},
                {'title': f'Report ({rules["weights"]["report"]} %)', 'pairs': _report_pairs(body['parts']['report'],
                                                                                            rules)},
                {'title': f'Deutsch ({rules["weights"]["german"]} %)', 'pairs': _german_pairs(body['parts']['german'],
                                                                                             rules)},
                {'title': f'SPV ({rules["weights"]["spv"]} %)', 'pairs': _rating_pairs('SPV', body['parts']['spv'])},
                {'title': f'Intern ({rules["weights"]["intern"]} %)',
                 'pairs': _rating_pairs('Intern', body['parts']['intern'])},
                {'title': 'Bewertungen' if body['all_ratings'] else 'Ihre Bewertungen', 'columns': rating_columns,
                 'rows': ratings, 'empty': 'Keine Bewertungen.'},
            ]}

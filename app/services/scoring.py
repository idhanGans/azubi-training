"""Bewertungs-Berechnung — die EINZIGE Stelle, die Punkte in Ergebnisse umrechnet.

Regeln (bestaetigt fuer Phase 7):
- Kategorie-Punkte: ohne Unterkategorien die vergebenen Punkte, sonst die
  Summe der Unterkategorien (deren Hoechstpunkte ergeben `max_score`).
- Kategorie-Prozent = Punkte / Hoechstpunkte * 100.
- Gesamt (`overall_percent`, 0–100) = gewichteter Mittelwert der
  Kategorie-Prozente: Summe(Prozent * Gewicht) / Summe(Gewichte),
  auf eine Nachkommastelle gerundet. `weighted` ist der Anteil einer
  Kategorie daran (Prozentpunkte).
- Bestanden = Gesamt >= Bestehensgrenze der Vorlage UND jede Kategorie mit
  Mindestpunkten hat sie erreicht.
- Fehlt ein Wert, ist die Bewertung unvollstaendig: Gesamt/Bestanden sind
  `None` (nur als Entwurf speicherbar).

Die Oberflaeche rechnet NICHT selbst: sie holt die Vorschau ueber
`POST /api/assessment-templates/<id>/evaluate`.
"""
from decimal import ROUND_HALF_UP, Decimal

_ONE = Decimal('0.1')


def _round(value):
    return value.quantize(_ONE, rounding=ROUND_HALF_UP)


def _f(value):
    return None if value is None else float(value)


def percent(score, max_score):
    """Punkte -> Prozent mit derselben Rundung wie ueberall (1 Nachkommastelle)."""
    return float(_round(Decimal(score) / Decimal(max_score) * 100))


def evaluate(template, points):
    """Ergebnis fuer `points` = {('category'|'criterion', id): Decimal} nach `template`."""
    total_weight = sum(c.weight for c in template.categories)
    categories, overall, complete = [], Decimal(0), True
    for cat in template.categories:
        criteria = [{'id': cr.id, 'name': cr.name, 'max_score': _f(cr.max_score),
                     'points': points.get(('criterion', cr.id))} for cr in cat.criteria]
        if criteria:
            given = [c['points'] for c in criteria if c['points'] is not None]
            score = sum(given, Decimal(0)) if len(given) == len(criteria) else None
            partial = sum(given, Decimal(0)) if given else None
        else:
            score = partial = points.get(('category', cat.id))
        percent = score / cat.max_score * 100 if score is not None else None
        if percent is None:
            complete = False
        else:
            overall += percent * cat.weight / total_weight
        categories.append({
            'id': cat.id, 'name': cat.name, 'max_score': _f(cat.max_score), 'weight': _f(cat.weight),
            'passing_score': _f(cat.passing_score),
            'score': _f(score), 'points_so_far': _f(partial),
            'percent': _f(_round(percent)) if percent is not None else None,
            'weighted': _f(_round(percent * cat.weight / total_weight)) if percent is not None else None,
            'passed': None if score is None else (cat.passing_score is None or score >= cat.passing_score),
            'criteria': [{**c, 'points': _f(c['points'])} for c in criteria],
        })
    overall_percent = _round(overall) if complete else None
    passed = None
    if complete:
        passed = overall_percent >= template.passing_percent and all(c['passed'] for c in categories)
    return {'categories': categories, 'complete': complete,
            'overall_percent': _f(overall_percent), 'passed': passed,
            'passing_percent': _f(template.passing_percent)}


def apply(assessment):
    """Ergebnis einer abgeschlossenen Bewertung speichern (nur hier wird es geschrieben)."""
    result = evaluate(assessment.template, assessment.points())
    assessment.overall_percent = None if result['overall_percent'] is None else Decimal(str(result['overall_percent']))
    assessment.passed = result['passed']
    return result

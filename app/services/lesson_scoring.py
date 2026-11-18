"""Modul-Bewertung nach der „Panduan Penilaian Deutschkurs" — die EINE Rechenstelle (Punkte + Level).

Je Modul-Termin und anwesendem Teilnehmer:
- Teil A · Sprechen: 5 Aspekte V R W F P je 1–3 Sterne (1 = trotz Hilfe nicht, 2 = Modulziel mit wenig Hilfe,
  3 = selbststaendig) -> 5–15 Punkte.
- Teil B · Lernverhalten: Pue (Puenktlichkeit 0–1), Mi (Mitarbeit 0–2), HA (Hausaufgabe 0–2) -> 0–5 Punkte.
  Keine Hausaufgabe an dem Tag (HA leer) zaehlt als volle 2 Punkte.
- Teil C · Rueckmeldung ohne Punkte: Staerke(n) und Ziel(e) (V R W F P oder L = Lernverhalten) + Notiz.
Leere Felder sind gewollt (Aspekt an dem Tag nicht gezeigt/bewertet): sie werden ignoriert — Durchschnitte je
Aspekt nehmen nur gefuellte Werte, ein Gesamt (und Level) gibt es nur, wenn alle 5 Aspekte, Pue und Mi gefuellt sind.
Gesamt = A + B (5–20). Level: A 18–20, B 15–17, C 12–14, D 5–11 — A und B nur, wenn KEIN Aspekt
1 Stern hat; sonst hoechstens C, auch bei 18 Punkten.
Wer die Regel aendert, aendert die Konstanten hier — die Oberflaeche liest sie ueber `rules()`.
"""
ASPECTS = ('v', 'r', 'w', 'f', 'p')            # Verstehen, Redemittel, Wortschatz, Fluessigkeit, Problemloesung
ASPECT_MIN, ASPECT_MAX = 1, 3
BEHAVIOR_MAX = {'pu': 1, 'mi': 2, 'ha': 2}      # Puenktlichkeit, Mitarbeit, Hausaufgabe
HA_WITHOUT_HOMEWORK = 2                         # keine Hausaufgabe aufgegeben = volle Punkte
FEEDBACK_CODES = ('V', 'R', 'W', 'F', 'P', 'L')  # L = Lernverhalten
LEVELS = (('A', 18), ('B', 15), ('C', 12), ('D', 5))
#: Hat ein Aspekt nur so viele Sterne, ist hoechstens dieses Level moeglich.
WEAK_ASPECT, CAPPED_LEVEL = 1, 'C'
#: Naechste Schritte (Rueckmeldung): Level D -> Begleitung, Level A -> Zusatzaufgaben.
COACHING_LEVEL, CHALLENGE_LEVEL = 'D', 'A'
#: Ohne diese Felder kein Gesamt (HA leer = keine Hausaufgabe, siehe oben).
SCORED = (*ASPECTS, 'pu', 'mi')
TOTAL_MIN = len(ASPECTS) * ASPECT_MIN
TOTAL_MAX = len(ASPECTS) * ASPECT_MAX + sum(BEHAVIOR_MAX.values())


def homework_points(ha):
    return HA_WITHOUT_HOMEWORK if ha is None else ha


def level_for(total, aspects):
    level = next(code for code, minimum in LEVELS if total >= minimum)
    capped = level in ('A', 'B') and any(value == WEAK_ASPECT for value in aspects)
    return (CAPPED_LEVEL if capped else level), capped


def evaluate(values):
    """values: v r w f p pu mi ha (ha None = keine Hausaufgabe) -> Punkte je Teil, Gesamt, Level.
    Fehlt einer der Werte aus `SCORED`, sind Punkte und Level None (`complete` False)."""
    if any(values.get(k) is None for k in SCORED):
        return {'part_a': None, 'part_b': None, 'total': None, 'level': None, 'capped': False, 'complete': False}
    aspects = [values[a] for a in ASPECTS]
    part_a = sum(aspects)
    part_b = values['pu'] + values['mi'] + homework_points(values['ha'])
    level, capped = level_for(part_a + part_b, aspects)
    return {'part_a': part_a, 'part_b': part_b, 'total': part_a + part_b, 'level': level, 'capped': capped,
            'complete': True}


def rules():
    """Die Regel-Zahlen fuer die Oberflaeche (Skalen, Level-Grenzen, Codes) — dort wird nichts nachgerechnet."""
    bounds, upper = [], TOTAL_MAX
    for code, minimum in LEVELS:
        bounds.append({'code': code, 'min': minimum, 'max': upper})
        upper = minimum - 1
    return {'aspects': list(ASPECTS), 'aspect_min': ASPECT_MIN, 'aspect_max': ASPECT_MAX,
            'behavior_max': BEHAVIOR_MAX, 'ha_without_homework': HA_WITHOUT_HOMEWORK,
            'feedback_codes': list(FEEDBACK_CODES), 'levels': bounds, 'capped_level': CAPPED_LEVEL,
            'coaching_level': COACHING_LEVEL, 'challenge_level': CHALLENGE_LEVEL,
            'total_min': TOTAL_MIN, 'total_max': TOTAL_MAX}

"""Modul-Bewertung je Termin (Panduan Penilaian Deutschkurs): Erfassungsliste, Speichern samt Anwesenheit,
offene Termine, Auswertung je Gruppe und Verlauf je Kandidat.

- Ein Termin kann mehrere Module abdecken: je Modul + Einheit eine Erfassungsliste („Blatt"). Ohne Angabe ist es
  das Modul des Termins mit seiner geplanten Einheit (wievielter nicht abgesagter Termin dieses Moduls im Kurs).
  Auswaehlbar sind die Module desselben Curriculums.
- Bewertet werden nur ANWESENDE (Anwesend/Verspaetet); wer fehlt, bekommt keine Sterne — schon vorhandene
  Bewertungen (aller Blaetter des Termins) fallen weg, sobald die Anwesenheit auf Abwesend/Entschuldigt geht.
- Leere Felder sind erlaubt und werden ignoriert (ohne alle Sterne + Pue + Mi kein Gesamt); HA ist Pflicht, sobald
  an dem Tag eine Hausaufgabe aufgegeben war und etwas bewertet wird. Staerke/Ziel: keiner, einer oder mehrere Codes.
- Gespeichert wird immer die ganze Gruppe (alle aktuellen Teilnehmer) in EINER Transaktion: Anwesenheit
  ueber `services/attendance.py` (dieselbe Regel, derselbe Verlauf, gilt fuer den ganzen Termin), Sterne hier.
  Fruehere Teilnehmer (Gruppenwechsel) duerfen mit, muessen aber nicht (`attendance.recordable`).
- Ein Blatt unter dem falschen Modul/der falschen Einheit laesst sich als Ganzes umhaengen (`move_sheet`).
Punkte und Level rechnet nur `lesson_scoring`.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, or_

from app.extensions import db
from app.models.attendance import STATUSES, Attendance
from app.models.course import Course
from app.models.course_module import CourseModule
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.lesson_rating import LessonRating, stored_codes
from app.models.trainee import Trainee
from app.services import attendance, lesson_scoring as scoring, validation as v
from app.services.local_time import day_range_utc, local_parts

NOTE_MAX = 1000
UNIT_MAX = 99
#: Offene Modul-Bewertung = Termine der letzten so vielen Tage, bei denen Anwesende noch keine Sterne haben.
OPEN_DAYS = attendance.OPEN_ATTENDANCE_DAYS
_LABELS = {'v': 'V · Verstehen', 'r': 'R · Redemittel', 'w': 'W · Wortschatz', 'f': 'F · Flüssigkeit',
           'p': 'P · Problemlösung', 'pu': 'Pü · Pünktlichkeit', 'mi': 'Mi · Mitarbeit', 'ha': 'HA · Hausaufgabe',
           'strength': 'Stärke', 'target': 'Ziel'}
_COMPLETE = and_(*(getattr(LessonRating, k).isnot(None) for k in scoring.SCORED))


# ---------- Einheit ----------

def unit_numbers(course_ids):
    """{session_id: Einheit} — je Kurs und Modul durchgezaehlt, abgesagte Termine zaehlen nicht (eine Abfrage)."""
    if not course_ids:
        return {}
    rows = (db.session.query(CourseSession.id, CourseSession.course_id, CourseSession.module_id)
            .filter(CourseSession.course_id.in_(list(course_ids)), CourseSession.status != 'CANCELLED')
            .order_by(CourseSession.starts_at, CourseSession.id))
    seen, units = Counter(), {}
    for sid, cid, mid in rows:
        if mid is not None:
            seen[(cid, mid)] += 1
            units[sid] = seen[(cid, mid)]
    return units


def session_dict(session, units):
    return {**session.to_dict(), 'unit': units.get(session.id)}


# ---------- Blaetter (Modul + Einheit) eines Termins ----------

def modules_for(session):
    """Waehlbare Module: die des Curriculums vom Modul des Termins (sonst des Kurses), in Curriculum-Reihenfolge."""
    base = session.module or session.course.module
    if base is None:
        return []
    return (CourseModule.query.filter(CourseModule.curriculum_id == base.curriculum_id, CourseModule.status != 'ARCHIVED')
            .order_by(CourseModule.position, CourseModule.id).all())


def sheets_of(session):
    """Schon bewertete Blaetter des Termins: [{module, unit, rated}] in Modul-Reihenfolge."""
    rows = (db.session.query(CourseModule.id, CourseModule.name, LessonRating.unit, func.count(LessonRating.id))
            .join(LessonRating, LessonRating.module_id == CourseModule.id)
            .filter(LessonRating.session_id == session.id)
            .group_by(CourseModule.id, LessonRating.unit)
            .order_by(CourseModule.position, CourseModule.id, LessonRating.unit))
    return [{'module': {'id': mid, 'name': name}, 'unit': unit, 'rated': n} for mid, name, unit, n in rows]


def suggested_unit(session, module_id):
    """Naechste Einheit dieses Moduls: nach der hoechsten schon bewerteten im Kurs bis zu diesem Termin; ohne
    Bewertungen beim Modul des Termins die geplante Einheit, sonst 1."""
    top = (db.session.query(func.max(LessonRating.unit))
           .join(CourseSession, CourseSession.id == LessonRating.session_id)
           .filter(CourseSession.course_id == session.course_id, LessonRating.module_id == module_id,
                   CourseSession.status != 'CANCELLED',
                   or_(CourseSession.starts_at < session.starts_at, CourseSession.id == session.id))
           .scalar())
    if top:
        return min(top + 1, UNIT_MAX)
    if module_id == session.module_id:
        return unit_numbers([session.course_id]).get(session.id) or 1
    return 1


def pick_sheet(session, data):
    """Modul + Einheit aus Abfrage/Body (`module_id`, `unit`): ohne Angabe das erste bewertete Blatt bzw. das Modul
    des Termins (sonst des Kurses). 400, wenn das Modul nicht zum Curriculum gehoert; ohne waehlbares Modul 409."""
    module_id = v.integer(data, 'module_id', 'Modul', 1, 2**31 - 1)
    unit = v.integer(data, 'unit', 'Einheit', 1, UNIT_MAX)
    if module_id is None:
        existing = sheets_of(session)
        if existing and unit is None:
            return db.session.get(CourseModule, existing[0]['module']['id']), existing[0]['unit']
        module_id = session.module_id or session.course.module_id
    choices = {m.id: m for m in modules_for(session)}
    if module_id is None or not choices:
        raise v.Conflict('Der Termin hat kein Modul — bitte zuerst ein Modul am Termin eintragen.', 'module_id')
    if module_id not in choices:
        raise v.ValidationError('Dieses Modul gehört nicht zum Curriculum des Kurses.', 'module_id')
    return choices[module_id], unit or suggested_unit(session, module_id)


# ---------- Erfassungsliste ----------

def sheet(session, module, unit):
    entries = attendance.sheet(session)
    ratings = {r.trainee_id: r for r in
               LessonRating.query.filter_by(session_id=session.id, module_id=module.id, unit=unit)}
    rows = [{**e, 'rating': ratings[e['trainee']['id']].to_dict() if e['trainee']['id'] in ratings else None}
            for e in entries]
    attended = sum(1 for e in entries if e['attendance'] and e['attendance']['status'] in attendance.ATTENDED)
    return {'session': session_dict(session, unit_numbers([session.course_id])),
            'sheet': {'module': {'id': module.id, 'name': module.name}, 'unit': unit},
            'sheets': sheets_of(session),
            'modules': [{'id': m.id, 'name': m.name} for m in modules_for(session)], 'unit_max': UNIT_MAX,
            'entries': rows,
            'homework_none': bool(ratings) and all(r.ha is None for r in ratings.values()),
            'rules': scoring.rules(),
            'summary': {'expected': sum(1 for e in entries if e['trainee']['in_course']),
                        'attended': attended, 'rated': len(ratings)}}


# ---------- Eingaben ----------

def _fail(name, message):
    raise v.ValidationError(f'{name}: {message}', 'entries')


def _optional(raw, key, low, high, name):
    try:
        return v.integer(raw, key, _LABELS[key], low, high)
    except v.ValidationError as err:
        _fail(name, err.message)


def _codes(raw, key, name):
    """Staerke/Ziel: None, ein Code oder Liste von Codes -> gespeicherte Form („V,R") oder None."""
    value = raw.get(key)
    codes = [] if value in (None, '') else [value] if isinstance(value, str) else value
    if not isinstance(codes, list) or any(c not in scoring.FEEDBACK_CODES for c in codes):
        _fail(name, f'„{_LABELS[key]}“: nur {" ".join(scoring.FEEDBACK_CODES)}.')
    return stored_codes(codes)


def read_rating(raw, homework_none, name):
    """Sterne + Lernverhalten + Rueckmeldung eines Anwesenden pruefen. Leere Felder sind erlaubt; ganz ohne Werte
    -> None (anwesend ohne Bewertung). HA Pflicht, wenn es eine Hausaufgabe gab und etwas bewertet wird."""
    values = {a: _optional(raw, a, scoring.ASPECT_MIN, scoring.ASPECT_MAX, name) for a in scoring.ASPECTS}
    values['pu'] = _optional(raw, 'pu', 0, scoring.BEHAVIOR_MAX['pu'], name)
    values['mi'] = _optional(raw, 'mi', 0, scoring.BEHAVIOR_MAX['mi'], name)
    ha = _optional(raw, 'ha', 0, scoring.BEHAVIOR_MAX['ha'], name)
    if homework_none and ha is not None:
        _fail(name, 'Heute ohne Hausaufgabe — „HA“ bitte leer lassen.')
    values['ha'] = ha
    values['strength'] = _codes(raw, 'strength', name)
    values['target'] = _codes(raw, 'target', name)
    if all(x is None for x in values.values()):
        return None
    if not homework_none and ha is None:
        _fail(name, f'Bitte „{_LABELS["ha"]}“ angeben (oder „keine Hausaufgabe“ wählen).')
    return values


def _has_scores(raw):
    return any(raw.get(k) not in (None, '', []) for k in LessonRating.VALUE_FIELDS)


def _note(raw, name):
    try:
        return v.text(raw, 'note', 'Notiz', NOTE_MAX)
    except v.ValidationError as err:
        _fail(name, err.message)


def _parse(session, data):
    homework_none = v.flag(data, 'homework_none', 'Keine Hausaufgabe')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        raise v.ValidationError('Bitte die Teilnehmer senden.', 'entries')
    members = dict(db.session.query(Trainee.id, Trainee.name)
                   .join(CourseParticipant, CourseParticipant.trainee_id == Trainee.id)
                   .filter(CourseParticipant.course_id == session.course_id, Trainee.archived_at.is_(None)))
    allowed = attendance.recordable(session)             # + fruehere Teilnehmer (Gruppenwechsel), freiwillig
    parsed = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise v.ValidationError('Ungültiger Eintrag.', 'entries')
        tid = raw.get('trainee_id')
        if not isinstance(tid, int) or tid not in allowed:
            raise v.ValidationError('Bewertung nur für Teilnehmer dieses Kurses.', 'entries')
        if tid in parsed:
            raise v.ValidationError('Jeder Kandidat darf nur einmal vorkommen.', 'entries')
        name, status = allowed[tid], raw.get('attendance')
        if status not in STATUSES:
            _fail(name, 'Bitte die Anwesenheit angeben.')
        late = None
        if status == 'LATE':
            try:
                late = v.integer(raw, 'minutes_late', 'Minuten zu spät', 1, 600)
            except v.ValidationError as err:
                _fail(name, err.message)
        if status in attendance.ATTENDED:
            rating = read_rating(raw, homework_none, name)
        elif _has_scores(raw):
            _fail(name, 'Nur anwesende Teilnehmer bekommen eine Bewertung.')
        else:
            rating = None
        parsed[tid] = {'name': name, 'status': status, 'minutes_late': late, 'note': _note(raw, name),
                       'rating': rating}
    missing = sorted(name for tid, name in members.items() if tid not in parsed)
    if missing:
        raise v.ValidationError(f'Bitte alle Teilnehmer erfassen — es fehlen: {", ".join(missing)}.', 'entries')
    return parsed


# ---------- Speichern ----------

def summary_text(values, module_name=None, unit=None):
    """Kurzform fuers Protokoll: „Modul 3 – … E1 · V3 R2 W3 F2 P2 · Pü1 Mi2 HA1 · 16 (B) · Stärke W · Ziel P"."""
    show = lambda x: '–' if x is None else x                            # noqa: E731
    result = scoring.evaluate(values)
    stars = ' '.join(f'{a.upper()}{show(values[a])}' for a in scoring.ASPECTS)
    total = f'{result["total"]} ({result["level"]})' if result['complete'] else 'ohne Gesamt'
    codes = {k: (values[k].replace(',', ' ') if isinstance(values[k], str) else ' '.join(values[k] or [])) or '–'
             for k in ('strength', 'target')}
    head = f'{module_name} E{unit} · ' if module_name else ''
    return (f'{head}{stars} · Pü{show(values["pu"])} Mi{show(values["mi"])} HA{show(values["ha"])} · {total} · '
            f'Stärke {codes["strength"]} · Ziel {codes["target"]}')


def record(session, module, unit, data, actor):
    """Ganze Gruppe fuer EIN Blatt (Modul + Einheit) speichern. Liefert (Anwesenheits-Aenderungen,
    Bewertungs-Aenderungen) fuers Protokoll — inkl. Bewertungen anderer Blaetter, die durch Fehlen wegfallen."""
    parsed = _parse(session, data)
    existing_att = {a.trainee_id: a for a in Attendance.query.filter_by(session_id=session.id)}
    att_entries = []
    for tid, p in parsed.items():
        attended = p['status'] in attendance.ATTENDED
        keep = existing_att[tid].note if tid in existing_att else None
        att_entries.append({'trainee_id': tid, 'status': p['status'], 'minutes_late': p['minutes_late'],
                            'note': keep if attended else p['note']})     # Grund des Fehlens steht an der Anwesenheit
    att_changes = attendance.record(session, att_entries, actor)

    existing = {r.trainee_id: r for r in
                LessonRating.query.filter_by(session_id=session.id, module_id=module.id, unit=unit)}
    changes = {}
    for tid, p in parsed.items():
        row, values = existing.get(tid), p['rating']
        if values is None:
            if row is not None:
                changes[p['name']] = [summary_text(row.values(), module.name, unit), None]
                db.session.delete(row)
            continue
        if row is None:
            db.session.add(LessonRating(session_id=session.id, module_id=module.id, unit=unit, trainee_id=tid,
                                        note=p['note'], **values))
            changes[p['name']] = [None, summary_text(values, module.name, unit)]
        elif {k: getattr(row, k) for k in values} != values or row.note != p['note']:
            old = summary_text(row.values(), module.name, unit) + (' · Notiz' if row.note else '')
            for key, value in values.items():
                setattr(row, key, value)
            row.note = p['note']
            changes[p['name']] = [old, summary_text(values, module.name, unit) + (' · Notiz' if p['note'] else '')]
    db.session.flush()
    changes.update(drop_unattended(session, taken=set(changes)))          # andere Blaetter dieses Termins
    return att_changes, changes


def move_sheet(session, module, unit, data):
    """Alle Bewertungen eines Blatts auf ein anderes Modul/eine andere Einheit desselben Curriculums umhaengen
    (`to_module_id`, `to_unit`). Liefert (Ziel-Modul, Ziel-Einheit, Anzahl). 409, wenn das Blatt leer ist oder das
    Ziel an diesem Termin schon Bewertungen hat (nie still zusammenfuehren)."""
    if v.integer(data, 'to_module_id', 'Neues Modul', 1, 2**31 - 1) is None:
        raise v.ValidationError('Bitte das neue Modul wählen.', 'to_module_id')
    v.integer(data, 'to_unit', 'Neue Einheit', 1, UNIT_MAX)
    target, target_unit = pick_sheet(session, {'module_id': data['to_module_id'], 'unit': data.get('to_unit')})
    if (target.id, target_unit) == (module.id, unit):
        raise v.ValidationError('Das Blatt steht schon unter diesem Modul und dieser Einheit.', 'to_module_id')
    rows = LessonRating.query.filter_by(session_id=session.id, module_id=module.id, unit=unit).all()
    if not rows:
        raise v.Conflict('Dieses Blatt hat noch keine Bewertungen.', 'module_id')
    if LessonRating.query.filter_by(session_id=session.id, module_id=target.id, unit=target_unit).count():
        raise v.Conflict(f'Für „{target.name}“, Einheit {target_unit}, gibt es an diesem Termin schon Bewertungen.',
                         'to_module_id')
    for row in rows:
        row.module_id, row.unit = target.id, target_unit
    db.session.flush()
    return target, target_unit, len(rows)


def drop_unattended(session, taken=()):
    """Nach einer Anwesenheits-Korrektur: Sterne von nun Fehlenden entfernen (alle Blaetter). {Name: [alt, None]} —
    ist der Name schon vergeben (`taken` oder zweites Blatt), steht Modul + Einheit dahinter."""
    rows = (db.session.query(LessonRating, Trainee.name)
            .join(Attendance, (Attendance.session_id == LessonRating.session_id)
                  & (Attendance.trainee_id == LessonRating.trainee_id))
            .join(Trainee, Trainee.id == LessonRating.trainee_id)
            .filter(LessonRating.session_id == session.id, Attendance.status.notin_(attendance.ATTENDED)).all())
    changes = {}
    for row, name in rows:
        key = name if name not in changes and name not in taken else f'{name} ({row.module.name} E{row.unit})'
        changes[key] = [summary_text(row.values(), row.module.name, row.unit), None]
        db.session.delete(row)
    return changes


def preview(data):
    """Live-Vorschau fuers Formular: {trainee_id: Ergebnis} — Eintraege ohne alle Punkte-Felder (bei Hausaufgabe
    auch HA) liefern `complete: False` (ohne Gesamt), leere/ungueltige None."""
    homework_none = v.flag(data, 'homework_none', 'Keine Hausaufgabe')
    entries = data.get('entries')
    if not isinstance(entries, list):
        raise v.ValidationError('Bitte die Einträge senden.', 'entries')
    results = {}
    for raw in entries:
        if not isinstance(raw, dict) or not isinstance(raw.get('trainee_id'), int):
            raise v.ValidationError('Ungültiger Eintrag.', 'entries')
        try:
            values = read_rating({**raw, 'ha': None}, True, '')
        except v.ValidationError:
            values = None
        result = None
        if values is not None:
            ha = raw.get('ha') if raw.get('ha') in (0, 1, 2) else None
            values['ha'] = None if homework_none else ha
            result = scoring.evaluate(values)
            if not homework_none and ha is None:
                result = scoring.evaluate({**values, 'v': None})          # HA fehlt -> ohne Gesamt
        results[str(raw['trainee_id'])] = result
    return results


# ---------- offene Termine ----------

def open_sessions(instructor_id=None, course_condition=None, days=OPEN_DAYS):
    """Vergangene Modul-Termine (letzte `days` Tage): noch ohne Anwesenheit oder Anwesende ohne Sterne."""
    now = datetime.now(timezone.utc)
    window = (CourseSession.starts_at <= now, CourseSession.starts_at > now - timedelta(days=days))
    att = (db.session.query(Attendance.session_id,
                            func.sum(case((Attendance.status.in_(attendance.ATTENDED), 1), else_=0)).label('n'))
           .group_by(Attendance.session_id).subquery())
    rated = (db.session.query(LessonRating.session_id, func.count(func.distinct(LessonRating.trainee_id)).label('n'))
             .group_by(LessonRating.session_id).subquery())
    members = (db.session.query(CourseParticipant.course_id, func.count(CourseParticipant.trainee_id).label('n'))
               .group_by(CourseParticipant.course_id).subquery())
    q = (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
         .join(members, members.c.course_id == CourseSession.course_id)
         .outerjoin(att, att.c.session_id == CourseSession.id)
         .outerjoin(rated, rated.c.session_id == CourseSession.id)
         .filter(CourseSession.status != 'CANCELLED', CourseSession.module_id.isnot(None),
                 Course.archived_at.is_(None), *window,
                 or_(att.c.session_id.is_(None), func.coalesce(rated.c.n, 0) < att.c.n)))
    if instructor_id is not None:
        q = q.filter(CourseSession.instructor_id == instructor_id)
    if course_condition is not None:
        q = q.filter(course_condition)
    sessions = q.order_by(CourseSession.starts_at.desc(), CourseSession.id.desc()).all()
    units = unit_numbers({s.course_id for s in sessions})
    return [session_dict(s, units) for s in sessions]


# ---------- Verlauf je Kandidat ----------

def history(trainee_id, course_condition=None, public=False):
    """Bewertungen eines Kandidaten, neueste zuerst — `public` ohne Notiz/Logins (Kandidat selbst)."""
    q = (db.session.query(LessonRating, CourseSession)
         .join(CourseSession, CourseSession.id == LessonRating.session_id)
         .join(Course, Course.id == CourseSession.course_id)
         .filter(LessonRating.trainee_id == trainee_id, CourseSession.status != 'CANCELLED'))
    if course_condition is not None:
        q = q.filter(course_condition)
    rows = q.order_by(CourseSession.starts_at.desc(), CourseSession.id.desc(), LessonRating.module_id.desc(),
                      LessonRating.unit.desc()).all()
    return [{**(r.public_dict() if public else r.to_dict()), 'session': s.public_dict()} for r, s in rows]


def latest_levels(trainee_ids, course_condition=None):
    """{trainee_id: (Level, Datum)} der jeweils neuesten Modul-Bewertung mit Gesamt (eine Abfrage)."""
    if not trainee_ids:
        return {}
    q = (db.session.query(LessonRating, CourseSession.starts_at)
         .join(CourseSession, CourseSession.id == LessonRating.session_id)
         .join(Course, Course.id == CourseSession.course_id)
         .filter(LessonRating.trainee_id.in_(list(trainee_ids)), CourseSession.status != 'CANCELLED',
                 Course.archived_at.is_(None), _COMPLETE))
    if course_condition is not None:
        q = q.filter(course_condition)
    q = q.distinct(LessonRating.trainee_id).order_by(LessonRating.trainee_id, CourseSession.starts_at.desc(),
                                                     LessonRating.unit.desc(), LessonRating.id.desc())
    return {r.trainee_id: (scoring.evaluate(r.values())['level'], local_parts(start)[0]) for r, start in q}


# ---------- Auswertung je Gruppe ----------

def _avg(values, digits=1):
    values = [x for x in values if x is not None]
    return round(sum(values) / len(values), digits) if values else None


def _rows(course_id, period):
    q = (db.session.query(LessonRating, CourseSession)
         .join(CourseSession, CourseSession.id == LessonRating.session_id)
         .filter(CourseSession.course_id == course_id, CourseSession.status != 'CANCELLED'))
    if period is not None:
        q = q.filter(CourseSession.starts_at >= period[0], CourseSession.starts_at < period[1])
    return q.order_by(CourseSession.starts_at, CourseSession.id, LessonRating.id).all()


def _averages(items):
    """items: [(werte, ergebnis)] -> Durchschnitt gesamt (nur Bewertungen mit Gesamt), je Aspekt und je
    Lernverhalten (nur gefuellte Werte; HA nur an Tagen mit Hausaufgabe)."""
    return {'total': _avg([res['total'] for _, res in items]),
            'aspects': {a: _avg([val[a] for val, _ in items], 2) for a in scoring.ASPECTS},
            'behavior': {'pu': _avg([val['pu'] for val, _ in items], 2), 'mi': _avg([val['mi'] for val, _ in items], 2),
                         'ha': _avg([val['ha'] for val, _ in items], 2)}}


def report(course, first=None, last=None):
    """Auswertung einer Gruppe im Zeitraum (ohne Zeitraum: ganzer Kurs) — wer steigt, wer faellt, welcher
    Aspekt schwach ist, wer Begleitung (Level D) bzw. Zusatzaufgaben (Level A) braucht. Feste Zahl an Abfragen."""
    period = day_range_utc(first, last) if first and last else None
    rows = _rows(course.id, period)
    previous = []
    if period is not None:                       # Trend: gleich langer Zeitraum direkt davor
        length = last - first + timedelta(days=1)
        previous = _rows(course.id, day_range_utc(first - length, first - timedelta(days=1)))
    units = unit_numbers([course.id])
    members = {tid for (tid,) in db.session.query(CourseParticipant.trainee_id).filter_by(course_id=course.id)}
    ids = members | {r.trainee_id for r, _ in rows}
    trainees = (Trainee.query.filter(Trainee.id.in_(ids)).order_by(func.lower(Trainee.name)).all() if ids else [])

    per_trainee, per_sheet, sheets = defaultdict(list), defaultdict(list), {}
    for rating, session in rows:
        item = (rating.values(), scoring.evaluate(rating.values()))
        per_trainee[rating.trainee_id].append((item, session, rating))
        key = (session.id, rating.module_id, rating.unit)
        per_sheet[key].append(item)
        sheets[key] = (session, rating.module)
    prev_total = defaultdict(list)
    for rating, _ in previous:
        prev_total[rating.trainee_id].append(scoring.evaluate(rating.values())['total'])

    participants = []
    for t in trainees:
        entries = per_trainee.get(t.id, [])
        items = [item for item, _, _ in entries]
        latest = None
        scored = [e for e in entries if e[0][1]['complete']]
        if scored:
            (values, result), session, rating = scored[-1]
            latest = {'date': local_parts(session.starts_at)[0], 'session_id': session.id,
                      'module': rating.module.name, 'unit': rating.unit,
                      'total': result['total'], 'level': result['level'],
                      'strength': values['strength'], 'target': values['target']}
        averages = _averages(items)
        before = _avg(prev_total.get(t.id, []))
        participants.append({
            'trainee': {'id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, 'nickname': t.nickname,
                        'in_course': t.id in members, 'archived': t.is_archived},
            'count': len(items), 'average': averages,
            'levels': dict(Counter(res['level'] for _, res in items if res['complete'])),
            'latest': latest, 'previous_total': before,
            'trend': round(averages['total'] - before, 1) if averages['total'] is not None and before is not None
            else None})

    every = [item for entries in per_trainee.values() for item, _, _ in entries]
    group = _averages(every)
    rated_aspects = {a: x for a, x in group['aspects'].items() if x is not None}
    weakest = min(rated_aspects.values()) if rated_aspects else None
    series = [{**session_dict(s, units), 'module': {'id': m.id, 'name': m.name}, 'unit': key[2],
               'rated': len(per_sheet[key]), 'average_total': _avg([res['total'] for _, res in per_sheet[key]])}
              for key, (s, m) in sheets.items()]
    latest_of = {p['trainee']['id']: p['latest'] for p in participants if p['latest']}
    return {
        'course': {'id': course.id, 'name': course.name, 'level': course.level.ref() if course.level else None},
        'period': {'from': first.isoformat() if first else None, 'to': last.isoformat() if last else None},
        'rules': scoring.rules(),
        'group': {'count': len(every), 'average': group,
                  'levels': dict(Counter(res['level'] for _, res in every if res['complete'])),
                  'weakest': [a for a, x in rated_aspects.items() if x == weakest]},
        'participants': participants,
        'sessions': series,
        'coaching': [p['trainee'] for p in participants
                     if latest_of.get(p['trainee']['id'], {}).get('level') == scoring.COACHING_LEVEL],
        'challenge': [p['trainee'] for p in participants
                      if latest_of.get(p['trainee']['id'], {}).get('level') == scoring.CHALLENGE_LEVEL],
    }

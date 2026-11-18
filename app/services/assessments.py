"""Bewertungen: anlegen, Punkte/Feedback pruefen, abschliessen, korrigieren.

Wer bewertet (bestaetigt fuer Phase 7):
- Dozenten nur Kandidaten ihrer eigenen Kurse (`scope`), Pruefer sind immer
  sie selbst; aendern duerfen sie nur Bewertungen, deren Pruefer sie sind.
- Studienleitung/Super-Admin (`candidate.view_all` + `assessment.edit`)
  bewerten jeden und waehlen den Pruefer.
Gerechnet wird nur in `app/services/scoring.py`.

Abgeschlossene Bewertungen aendern sich nur ueber Abschliessen und Korrektur: die Datenbank lehnt jede
andere Aenderung an Ergebnis, Punkten und benutzter Vorlage ab (Migration 0015), diese beiden Wege
schalten sie mit `allow_result_change()` fuer ihre Transaktion frei und protokollieren Alt -> Neu.
Den Verlauf je Bewertung liefert `history()`.
"""
from datetime import date

from sqlalchemy import text

from app.extensions import db
from app.models.activity import ActivityLog
from app.models.assessment import Assessment
from app.models.assessment_score import AssessmentScore
from app.models.assessment_template import AssessmentTemplate
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.instructor import Instructor
from app.models.trainee import Trainee
from app.services import assessment_templates as templates, scope, validation as v
from app.services.activity import actor_names
from app.services.local_time import today

FEEDBACK_LABELS = {'strengths': 'Stärken', 'improvements': 'Verbesserungsbereiche',
                   'recommendations': 'Empfehlungen', 'general_feedback': 'Allgemeines Feedback'}
MAX_TEXT = 4000
EARLIEST = date(2020, 1, 1)


def allow_result_change():
    """Nur Abschliessen und Korrektur: Ergebnis/Punkte einer abgeschlossenen Bewertung fuer DIESE
    Transaktion freigeben (sonst lehnt der Trigger aus Migration 0015 ab)."""
    db.session.execute(text("SET LOCAL azubi.assessment_correction = 'on'"))


#: Aktionen, die im Verlauf einer Bewertung erscheinen (Entwurfs-Speichern wird nicht protokolliert).
HISTORY_ACTIONS = ('assessment.create', 'assessment.finalize', 'assessment.correct')


def history(assessment):
    """Verlauf EINER Bewertung (aelteste zuerst): wer, wann, was (Alt -> Neu), Grund — Eintraege des Verlaufs
    in derselben Form wie `/api/activity` (Oberflaeche: `ActivityList`)."""
    rows = (ActivityLog.query
            .filter(ActivityLog.entity_type == 'trainee', ActivityLog.entity_id == assessment.trainee_id,
                    ActivityLog.action.in_(HISTORY_ACTIONS),
                    ActivityLog.detail['assessment_id'].as_integer() == assessment.id)
            .order_by(ActivityLog.created_at, ActivityLog.id).all())
    names = actor_names({r.actor for r in rows})
    return [{**r.to_dict(), 'actor_name': names.get(r.actor)} for r in rows]


def can_edit(identity, assessment):
    if not identity.can('assessment.edit'):
        return False
    return scope.sees_all(identity) or assessment.instructor_id == identity.instructor_id


def _instructor(data, identity, current=None):
    raw = data.get('instructor_id')
    if not scope.sees_all(identity):
        if identity.instructor_id is None:
            raise v.ValidationError('Nur Dozenten mit Dozenten-Datensatz können bewerten.', 'instructor_id')
        if raw not in (None, '') and str(raw) != str(identity.instructor_id):
            raise v.ValidationError('Als Dozent sind Sie immer selbst der Prüfer.', 'instructor_id')
        return identity.instructor_id
    if raw in (None, ''):
        if current:
            return current
        if identity.instructor_id:
            return identity.instructor_id
        raise v.ValidationError('Bitte einen Prüfer auswählen.', 'instructor_id')
    try:
        instructor = db.session.get(Instructor, int(raw))
    except (TypeError, ValueError):
        instructor = None
    if instructor is None or (instructor.is_archived and instructor.id != current):
        raise v.ValidationError('Bitte einen gültigen Prüfer auswählen.', 'instructor_id')
    return instructor.id


def _course(data, trainee_id, identity):
    raw = data.get('course_id')
    if raw in (None, ''):
        return None
    try:
        course = db.session.get(Course, int(raw))
    except (TypeError, ValueError):
        course = None
    if course is None or not scope.can_see_course(identity, course) or \
            db.session.get(CourseParticipant, (course.id, trainee_id)) is None:
        raise v.ValidationError('Bitte einen Kurs des Kandidaten auswählen.', 'course_id')
    return course.id


def _date(data):
    day = v.day(data, 'assessed_on', 'Datum', earliest=EARLIEST, latest=date(today().year + 1, 12, 31))
    if day is None:
        raise v.ValidationError('Bitte „Datum“ ausfüllen.', 'assessed_on')
    return day


def read_new(data, identity, actor):
    try:
        trainee = db.session.get(Trainee, int(data.get('trainee_id')))
    except (TypeError, ValueError):
        trainee = None
    if trainee is None or not scope.can_see_trainee(identity, trainee.id):
        raise v.ValidationError('Bitte einen Kandidaten auswählen.', 'trainee_id')
    if trainee.is_archived:
        raise v.ValidationError('Der Kandidat ist archiviert.', 'trainee_id')
    try:
        template = db.session.get(AssessmentTemplate, int(data.get('template_id')))
    except (TypeError, ValueError):
        template = None
    templates.check_usable(template)
    assessment = Assessment(trainee_id=trainee.id, template_id=template.id, status='DRAFT',
                            instructor_id=_instructor(data, identity),
                            course_id=_course(data, trainee.id, identity),
                            assessed_on=_date(data), created_by=actor)
    for key, value in read_texts(data).items():
        setattr(assessment, key, value)
    return assessment


def read_changes(data, assessment, identity):
    """Aenderbare Kopf-Felder: Datum immer, Pruefer + Kurs nur im Entwurf."""
    values = {}
    if 'assessed_on' in data:
        values['assessed_on'] = _date(data)
    if assessment.status == 'DRAFT':
        if 'instructor_id' in data:
            values['instructor_id'] = _instructor(data, identity, assessment.instructor_id)
        if 'course_id' in data:
            values['course_id'] = _course(data, assessment.trainee_id, identity)
    values.update(read_texts(data, partial=True))
    return values


def read_texts(data, partial=False):
    fields = {**FEEDBACK_LABELS, 'internal_note': 'Interne Notiz'}
    return {name: v.text(data, name, label, MAX_TEXT) for name, label in fields.items()
            if not partial or name in data}


def read_scores(template, raw):
    """[{category_id|criterion_id, points}] -> {key: Decimal|None}; None entfernt einen Wert."""
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise v.ValidationError('Ungültige Punkte.', 'scores')
    fields = {}
    for cat in template.categories:
        if cat.criteria:
            for cr in cat.criteria:
                fields[('criterion', cr.id)] = (f'{cat.name} – {cr.name}', cr.max_score)
        else:
            fields[('category', cat.id)] = (cat.name, cat.max_score)
    result = {}
    for item in raw:
        if not isinstance(item, dict):
            raise v.ValidationError('Ungültige Punkte.', 'scores')
        kind = 'criterion' if item.get('criterion_id') not in (None, '') else 'category'
        try:
            key = (kind, int(item.get(f'{kind}_id')))
        except (TypeError, ValueError):
            key = None
        if key not in fields or key in result:
            raise v.ValidationError('Die Punkte passen nicht zur Vorlage.', 'scores')
        label, max_score = fields[key]
        try:
            result[key] = templates.half_points(item, 'points', label, 0, float(max_score))
        except v.ValidationError as err:
            raise v.ValidationError(err.message, 'scores') from None
    return result


def apply_scores(assessment, parsed):
    """Punkte setzen/aendern/entfernen. Liefert {Feldname: [alt, neu]} fuer das Protokoll."""
    rows = {s.key(): s for s in assessment.scores}
    names = _field_names(assessment.template)
    changes = {}
    for key, points in parsed.items():
        row = rows.get(key)
        old = row.points if row else None
        if old == points:
            continue
        changes[names[key]] = [None if old is None else float(old), None if points is None else float(points)]
        if points is None:
            assessment.scores.remove(row)
        elif row:
            row.points = points
        else:
            assessment.scores.append(AssessmentScore(
                category_id=key[1] if key[0] == 'category' else None,
                criterion_id=key[1] if key[0] == 'criterion' else None, points=points))
    return changes


def _field_names(template):
    names = {}
    for cat in template.categories:
        names[('category', cat.id)] = cat.name
        for cr in cat.criteria:
            names[('criterion', cr.id)] = f'{cat.name} – {cr.name}'
    return names


def check_finalizable(assessment, result):
    if not result['complete']:
        missing = [c['name'] for c in result['categories'] if c['score'] is None]
        raise v.ValidationError('Zum Abschließen fehlen noch Punkte: ' + ', '.join(missing) + '.', 'scores')
    if assessment.assessed_on > today():
        raise v.ValidationError('Eine Bewertung mit Datum in der Zukunft kann nicht abgeschlossen werden.',
                                'assessed_on')
    if assessment.trainee.is_archived:
        raise v.Conflict('Der Kandidat ist archiviert.', 'trainee_id')

"""Fortschritt eines Kandidaten — die EINE Stelle fuer Fertigkeiten- und Modul-Fortschritt.

Fertigkeiten (Lesen, Hören, …):
- Quelle sind nur ABGESCHLOSSENE Bewertungen; die Kategorie-Punkte kommen aus
  `scoring.evaluate` (keine zweite Rechnung).
- Je Bewertung und Fertigkeit: Summe der Punkte / Summe der Hoechstpunkte aller
  Kategorien mit dieser Fertigkeit (`assessment_category.skill`) in Prozent.
  Kategorien ohne Fertigkeit zaehlen im Gesamtergebnis, hier nicht.
- „Aktuell" ist der Wert der NEUESTEN Bewertung mit dieser Fertigkeit,
  „Veraenderung" der Unterschied zur ersten.

Module:
- Je Curriculum der Kurs des Kandidaten mit dem am weitesten fortgeschrittenen
  aktuellen Modul. Abgeschlossen sind alle (nicht archivierten) Module VOR dem
  aktuellen Modul des Kurses; ist der Kurs abgeschlossen, auch das aktuelle.
"""
from decimal import Decimal

from sqlalchemy.orm import lazyload

from app.extensions import db
from app.models.assessment import Assessment
from app.models.assessment_category import SKILLS
from app.models.course import Course
from app.models.course_module import CourseModule
from app.models.course_participant import CourseParticipant
from app.services import attendance, scoring


def skill_values(template, result):
    """{skill: Prozent} fuer EINE bewertete Vorlage (`result` aus `scoring.evaluate`)."""
    categories = {c.id: c for c in template.categories}
    totals = {}
    for entry in result['categories']:
        category = categories[entry['id']]
        if category.skill is None or entry['score'] is None:
            continue
        score, max_score = totals.get(category.skill, (Decimal(0), Decimal(0)))
        totals[category.skill] = (score + Decimal(str(entry['score'])), max_score + category.max_score)
    return {skill: scoring.percent(score, max_score) for skill, (score, max_score) in totals.items()}


def assessments(trainee_id):
    """Verlauf der abgeschlossenen Bewertungen + Fertigkeiten (aelteste zuerst)."""
    rows = (Assessment.query.filter_by(trainee_id=trainee_id, status='FINAL')
            .order_by(Assessment.assessed_on, Assessment.id).all())
    trend, series = [], {code: [] for code in SKILLS}
    for a in rows:
        point = {'assessment_id': a.id, 'date': a.assessed_on.isoformat(), 'template': a.template.name}
        trend.append({**point, 'overall_percent': float(a.overall_percent), 'passed': a.passed})
        for skill, value in skill_values(a.template, scoring.evaluate(a.template, a.points())).items():
            series[skill].append({**point, 'percent': value})
    skills = []
    for code in SKILLS:
        points = series[code]
        if points:
            skills.append({'skill': code, 'current': points[-1]['percent'], 'current_date': points[-1]['date'],
                           'first': points[0]['percent'],
                           'change': round(points[-1]['percent'] - points[0]['percent'], 1),
                           'count': len(points), 'series': points})
    return {'skills': skills, 'assessment_trend': trend}


def modules(trainee_id, course_condition=None):
    """Modul-Fortschritt je Curriculum (siehe Modul-Doku oben)."""
    return modules_of([trainee_id], course_condition).get(trainee_id, [])


def modules_of(trainee_ids, course_condition=None):
    """Wie `modules`, fuer viele Kandidaten zusammen: {trainee_id: [...]} — eine Query fuer die Kurse,
    eine fuer die Module, jeder Kurs wird nur einmal ausgewertet (Team-Uebersicht, Berichte)."""
    if not trainee_ids:
        return {}
    q = (db.session.query(CourseParticipant.trainee_id, Course)
         .join(Course, CourseParticipant.course_id == Course.id)
         .filter(CourseParticipant.trainee_id.in_(list(trainee_ids)), Course.archived_at.is_(None),
                 Course.module_id.isnot(None)))
    if course_condition is not None:
        q = q.filter(course_condition)
    best = {}
    for tid, course in q.all():
        module = course.module
        rank = (module.position, course.status == 'COMPLETED')
        mine = best.setdefault(tid, {})
        current = mine.get(module.curriculum_id)
        if current is None or rank > current[0]:
            mine[module.curriculum_id] = (rank, course)
    catalog = curriculum_modules({course.module.curriculum_id for mine in best.values() for _, course in mine.values()})
    done_by_course, result = {}, {}
    for tid, mine in best.items():
        entries = []
        for _, course in mine.values():
            if course.id not in done_by_course:
                done_by_course[course.id] = course_completion(course, catalog[course.module.curriculum_id])
            curriculum = course.module.curriculum
            entries.append({
                'curriculum': {'id': curriculum.id, 'program': curriculum.program.name, 'level': curriculum.level.ref()},
                'course': {'id': course.id, 'name': course.name, 'status': course.status}, **done_by_course[course.id]})
        result[tid] = sorted(entries, key=lambda r: (r['curriculum']['program'], r['curriculum']['level']['code']))
    return result


def curriculum_modules(curriculum_ids):
    """{curriculum_id: [nicht archivierte Module in Reihenfolge]} — eine Query."""
    result = {cid: [] for cid in curriculum_ids}
    if result:
        for m in (CourseModule.query.options(lazyload(CourseModule.curriculum))
                  .filter(CourseModule.curriculum_id.in_(list(result)), CourseModule.status != 'ARCHIVED')
                  .order_by(CourseModule.position, CourseModule.id)):
            result[m.curriculum_id].append(m)
    return result


def course_completion(course, module_list=None):
    """Modul-Stand EINES Kurses (siehe Modul-Doku oben): Liste mit done/current/open + Zaehler.
    `module_list` = vorab geladene Module seines Curriculums (`curriculum_modules`, sonst eine Query)."""
    current = course.module
    done_current = course.status == 'COMPLETED'
    if module_list is None:
        module_list = curriculum_modules([current.curriculum_id])[current.curriculum_id]
    items = []
    for m in module_list:
        if m.position < current.position or (m.id == current.id and done_current):
            state = 'done'
        elif m.id == current.id:
            state = 'current'
        else:
            state = 'open'
        items.append({'id': m.id, 'name': m.name, 'state': state})
    completed = sum(1 for i in items if i['state'] == 'done')
    return {'current': None if done_current else {'id': current.id, 'name': current.name},
            'completed': completed, 'total': len(items),
            'percent': scoring.percent(completed, len(items)) if items else None, 'items': items}


def overview(trainee_id, course_condition=None, with_assessments=True, with_attendance=True):
    """Alles fuer die Fortschritts-Ansicht; Teile nur, wenn die Rolle sie sehen darf."""
    body = {'modules': modules(trainee_id, course_condition)}
    if with_assessments:
        body.update(assessments(trainee_id))
    if with_attendance:
        body['attendance'] = {'stats': attendance.stats_for(trainee_id, course_condition),
                              'weeks': attendance.weekly(trainee_id, course_condition)}
    return body

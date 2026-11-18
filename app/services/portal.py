"""Kandidaten-Portal: was ein Kandidat von SEINEN Kursen und Modulen sehen darf.

Grundlage sind nur die eigenen, nicht archivierten Kurse (`course_participant`).
Module/Material: das Curriculum des aktuellen Kursmoduls — dieselbe Menge wie
im Fortschritt (`services/progress.py`), nicht archivierte Module und Materialien.
Andere Kandidaten tauchen nirgends auf (auch nicht als Mitschueler-Liste).
"""
from sqlalchemy import func

from app.extensions import db
from app.models.course import Course
from app.models.course_module import CourseModule
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.material import Material
from app.models.training_report import TrainingReport
from app.services import progress
from app.services.local_time import day_range_utc, today


def courses(trainee_id):
    """Eigene, nicht archivierte Kurse (nach Name)."""
    return (Course.query.join(CourseParticipant, CourseParticipant.course_id == Course.id)
            .filter(CourseParticipant.trainee_id == trainee_id, Course.archived_at.is_(None))
            .order_by(func.lower(Course.name)).all())


def curriculum_ids(trainee_id):
    return {c.module.curriculum_id for c in courses(trainee_id) if c.module is not None}


def modules(trainee_id):
    """Je Curriculum: Module mit Stand (erledigt/aktuell/offen), Lernzielen und Material."""
    entries = progress.modules(trainee_id)
    states = {i['id']: i['state'] for entry in entries for i in entry['items']}
    result = []
    for entry in entries:
        ids = [i['id'] for i in entry['items']]
        rows = {m.id: m for m in CourseModule.query.filter(CourseModule.id.in_(ids))} if ids else {}
        materials = {}
        for m in (Material.query.filter(Material.module_id.in_(ids), Material.archived_at.is_(None),
                                        Material.team_only.is_(False))
                  .order_by(Material.position, Material.id)) if ids else []:
            materials.setdefault(m.module_id, []).append(m.public_dict())
        result.append({**{k: entry[k] for k in ('curriculum', 'course', 'current', 'completed', 'total', 'percent')},
                       'modules': [{'id': mid, 'name': rows[mid].name, 'description': rows[mid].description,
                                    'duration_hours': float(rows[mid].duration_hours)
                                    if rows[mid].duration_hours is not None else None,
                                    'learning_objectives': list(rows[mid].learning_objectives or []),
                                    'state': states[mid], 'materials': materials.get(mid, [])} for mid in ids]})
    return result


def material_visible(trainee_id, material):
    """Nur nicht archiviertes Material fuer Kandidaten (nicht `team_only`) nicht archivierter Module aus einem
    Curriculum eigener Kurse."""
    module = db.session.get(CourseModule, material.module_id)
    return (material.archived_at is None and not material.team_only and module.status != 'ARCHIVED'
            and module.curriculum_id in curriculum_ids(trainee_id))


def next_sessions(course_ids, limit):
    if not course_ids:
        return []
    return (CourseSession.query.filter(CourseSession.course_id.in_(course_ids), CourseSession.status != 'CANCELLED',
                                       CourseSession.ends_at > db.func.now())
            .order_by(CourseSession.starts_at).limit(limit).all())


def today_tasks(trainee_id, course_ids):
    """„Heute" auf der Startseite: eigene Termine heute (Ortszeit, nicht abgesagt) und ob der
    Tages-Report fuer heute schon abgegeben ist — beantwortet „Was muss ich heute tun?"."""
    day = today()
    start, end = day_range_utc(day, day)
    sessions = (CourseSession.query.filter(CourseSession.course_id.in_(course_ids), CourseSession.status != 'CANCELLED',
                                           CourseSession.starts_at >= start, CourseSession.starts_at < end)
                .order_by(CourseSession.starts_at).all()) if course_ids else []
    report_done = db.session.query(TrainingReport.id).filter_by(trainee_id=trainee_id,
                                                                period=day.isoformat()).first() is not None
    return {'date': day.isoformat(), 'sessions': [s.public_dict() for s in sessions], 'report_done': report_done}

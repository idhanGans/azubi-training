"""Reichweite: WELCHE Kandidaten und Kurse ein Nutzer sehen darf.

Die Berechtigung (`candidate.view`, `schedule.view` …) sagt, OB jemand eine
Route nutzen darf; hier steht, auf welche Datensaetze sie sich erstreckt:

- mit `candidate.view_all` (HR, Studienleitung, Geschaeftsleitung, Admin): alle
- sonst (Dozent): nur die eigenen, nicht archivierten Kurse und deren Teilnehmer.
  „Eigen" ist ein Kurs, dem er zugeordnet ist ODER in dem er einen nicht
  abgesagten Termin gibt (Vertretung). Ohne Dozenten-Datensatz: nichts.

Jede Route mit Kandidaten- oder Kursdaten filtert ueber diese Funktionen.
"""
from sqlalchemy import false, select

from app.extensions import db
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession


def sees_all(identity):
    return identity.can('candidate.view_all')


def course_condition(identity):
    """SQL-Bedingung auf `Course` — None heisst: keine Einschraenkung."""
    if sees_all(identity):
        return None
    if identity.instructor_id is None:
        return false()
    return own_courses(identity.instructor_id)


def own_courses(instructor_id):
    """Kurse eines Dozenten: zugeordnet ODER mit eigenem, nicht abgesagtem Termin; nicht archiviert."""
    teaches = (select(CourseSession.course_id)
               .where(CourseSession.instructor_id == instructor_id, CourseSession.status != 'CANCELLED'))
    return ((Course.instructor_id == instructor_id) | Course.id.in_(teaches)) & Course.archived_at.is_(None)


def trainee_ids(identity):
    """Subquery der sichtbaren Kandidaten-IDs — None heisst: alle."""
    condition = course_condition(identity)
    if condition is None:
        return None
    return (select(CourseParticipant.trainee_id)
            .join(Course, Course.id == CourseParticipant.course_id)
            .where(condition))


def restrict(query, trainee_column, identity):
    """`query` auf die sichtbaren Kandidaten begrenzen."""
    visible = trainee_ids(identity)
    return query if visible is None else query.filter(trainee_column.in_(visible))


def can_see_trainee(identity, trainee_id):
    visible = trainee_ids(identity)
    if visible is None:
        return True
    return db.session.execute(visible.where(CourseParticipant.trainee_id == trainee_id).limit(1)).first() is not None


def can_see_course(identity, course):
    condition = course_condition(identity)
    if condition is None:
        return True
    return db.session.query(Course.id).filter(Course.id == course.id, condition).first() is not None

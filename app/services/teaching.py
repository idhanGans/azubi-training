"""„Mein Unterricht" eines Dozenten: Termine, Unterrichtszeit im Monat, offene Anwesenheit/Bewertungen,
Kurse und Teilnehmer — die Kennzahlen dieser Seite entstehen nur hier."""
from datetime import timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.trainee import Trainee
from app.services import attendance, courses as course_svc, lesson_ratings, scheduling, scope
from app.services.local_time import day_range_utc, day_start_utc, today

#: „Kommende Termine" reichen so viele Tage voraus.
UPCOMING_DAYS = 14


def _my_sessions(instructor_id, starts, ends):
    """Eigene (als Dozent eingetragene), nicht abgesagte Termine nicht archivierter Kurse."""
    return (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
            .filter(CourseSession.instructor_id == instructor_id, CourseSession.status != 'CANCELLED',
                    Course.archived_at.is_(None), CourseSession.starts_at < ends, CourseSession.ends_at > starts)
            .order_by(CourseSession.starts_at).all())


def _participants(course_names):
    """Aktive Teilnehmer der eigenen Kurse, je Person einmal mit all ihren Kursen."""
    rows = (db.session.query(Trainee, CourseParticipant.course_id)
            .join(CourseParticipant, CourseParticipant.trainee_id == Trainee.id)
            .filter(CourseParticipant.course_id.in_(list(course_names)), Trainee.archived_at.is_(None))
            .order_by(func.lower(Trainee.name)).all()) if course_names else []
    result = {}
    for trainee, course_id in rows:
        entry = result.setdefault(trainee.id, {
            'id': trainee.id, 'candidate_no': trainee.candidate_no, 'name': trainee.name,
            'nickname': trainee.nickname,
            'current_level': trainee.current_level.ref() if trainee.current_level else None,
            'status': trainee.status.ref() if trainee.status else None, 'courses': []})
        entry['courses'].append({'id': course_id, 'name': course_names[course_id]})
    return list(result.values())


def overview(instructor):
    courses = Course.query.filter(scope.own_courses(instructor.id)).order_by(func.lower(Course.name)).all()
    counts = course_svc.participant_counts([c.id for c in courses])
    participants = _participants({c.id: c.name for c in courses})

    day = today()
    today_sessions = _my_sessions(instructor.id, *day_range_utc(day, day))
    upcoming = _my_sessions(instructor.id, day_start_utc(day + timedelta(days=1)),
                            day_start_utc(day + timedelta(days=UPCOMING_DAYS + 1)))
    month_start = day.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month = _my_sessions(instructor.id, day_start_utc(month_start), day_start_utc(next_month))
    open_attendance = attendance.open_sessions(instructor.id)
    open_lessons = lesson_ratings.open_sessions(instructor.id)
    drafts = (Assessment.query.filter_by(instructor_id=instructor.id, status='DRAFT')
              .order_by(Assessment.assessed_on, Assessment.id).all())
    return {
        'instructor': instructor.to_dict(),
        'stats': {'course_count': len(courses),
                  'running_count': sum(1 for c in courses if c.status == 'RUNNING'),
                  'participant_count': len(participants),
                  'today_count': len(today_sessions),
                  'hours_month': scheduling.hours(month),
                  'open_attendance_count': len(open_attendance),
                  'open_lesson_count': len(open_lessons),
                  'open_assessment_count': len(drafts)},
        'windows': {'upcoming_days': UPCOMING_DAYS, 'open_attendance_days': attendance.OPEN_ATTENDANCE_DAYS,
                    'open_lesson_days': lesson_ratings.OPEN_DAYS},
        'open_assessments': [a.summary() for a in drafts],
        'open_attendance': [s.to_dict() for s in open_attendance],
        'open_lesson_ratings': open_lessons,
        'today': [s.to_dict() for s in today_sessions],
        'upcoming': [s.to_dict() for s in upcoming],
        'courses': [{**c.to_dict(), 'participant_count': counts.get(c.id, 0)} for c in courses],
        'participants': participants,
    }

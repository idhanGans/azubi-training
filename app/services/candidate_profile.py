"""Kandidatenprofil fuers Team: Stammdaten, Kurse, naechste Termine, Trainings-Reports und — je nach Recht —
Mitarbeiter-Bewertungen, Bewertungen, Modul-Bewertungen, Anwesenheit (fehlt das Recht, fehlt der Schluessel ganz)."""
from app.extensions import db
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.staff_rating import StaffRating
from app.models.training_report import TrainingReport
from app.services import attendance, courses, lesson_ratings, lesson_scoring, scope, training_stats

UPCOMING_LIMIT = 5
RECENT_REPORTS = 10
RATINGS_LIMIT = 50


def _upcoming_sessions(trainee_id):
    return (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
            .join(CourseParticipant, CourseParticipant.course_id == CourseSession.course_id)
            .filter(CourseParticipant.trainee_id == trainee_id, Course.archived_at.is_(None),
                    CourseSession.status != 'CANCELLED', CourseSession.ends_at > db.func.now())
            .order_by(CourseSession.starts_at).limit(UPCOMING_LIMIT).all())


def profile(trainee, identity):
    cid = trainee.id
    recent = (TrainingReport.query.filter_by(trainee_id=cid).order_by(TrainingReport.created_at.desc())
              .limit(RECENT_REPORTS).all())
    body = {
        'candidate': trainee.to_dict(),
        'courses': courses.courses_of_trainees([cid]).get(cid, []),
        'upcoming_sessions': [s.to_dict() for s in _upcoming_sessions(cid)],
        'training': {**training_stats.report_summary(cid), 'recent_reports': [r.to_dict() for r in recent]},
    }
    if identity.can('assessment.view'):
        body['ratings'] = [r.to_dict() for r in StaffRating.query.filter_by(trainee_id=cid)
                           .order_by(StaffRating.created_at.desc()).limit(RATINGS_LIMIT)]
        body['assessments'] = [a.summary() for a in Assessment.query.filter_by(trainee_id=cid)
                               .order_by(Assessment.assessed_on, Assessment.id)]
        body['lesson_ratings'] = {'ratings': lesson_ratings.history(cid, scope.course_condition(identity)),
                                  'rules': lesson_scoring.rules()}
    if identity.can('attendance.view'):
        condition = scope.course_condition(identity)
        body['attendance'] = {'stats': attendance.stats_for(cid, condition),
                              'recent': [{**a.to_dict(), 'session': s.public_dict()}
                                         for a, s in attendance.recent(cid, condition)]}
    return body

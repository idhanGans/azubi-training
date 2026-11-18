from datetime import timedelta

from app.extensions import db
from app.models.common import iso, utcnow
from app.services.local_time import local_parts

#: Termin-Status. Abgesagte Termine bleiben erhalten (mit Grund), zaehlen aber
#: bei Zeitkonflikten nicht mehr.
STATUSES = ('SCHEDULED', 'COMPLETED', 'CANCELLED')
#: Anwesenheit laesst sich ab so viel vor Beginn erfassen (Pruefung: services/attendance.py).
ATTENDANCE_LEAD = timedelta(minutes=15)


class CourseSession(db.Model):
    """Ein Unterrichtstermin eines Kurses.

    Zeiten liegen als `timestamptz` (UTC) in der DB; eingegeben und angezeigt
    werden sie in Europe/Berlin (`app/services/local_time.py`). Teilnehmer sind
    die des Kurses. Dozent und Modul werden beim Anlegen vom Kurs uebernommen
    und koennen je Termin abweichen (Vertretung, anderes Thema).
    """
    __tablename__ = 'course_session'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey('course_module.id'), nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('instructor.id'), nullable=True, index=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    room = db.Column(db.String(80), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    online_url = db.Column(db.String(1000), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='SCHEDULED')
    cancel_reason = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    course = db.relationship('Course', lazy='joined')
    module = db.relationship('CourseModule', lazy='joined')
    instructor = db.relationship('Instructor', lazy='joined')

    @property
    def duration_minutes(self):
        return int((self.ends_at - self.starts_at).total_seconds() // 60)

    def public_dict(self):
        """Was Kandidaten sehen duerfen — ohne interne Notizen und Verwaltungsfelder."""
        day, start = local_parts(self.starts_at)
        _, end = local_parts(self.ends_at)
        return {'id': self.id, 'date': day, 'start': start, 'end': end,
                'starts_at': iso(self.starts_at), 'ends_at': iso(self.ends_at),
                'duration_minutes': self.duration_minutes,
                'course': {'id': self.course.id, 'name': self.course.name, 'level': self.course.level.ref()},
                'module': {'id': self.module.id, 'name': self.module.name} if self.module else None,
                'instructor': self.instructor.ref() if self.instructor else None,
                'room': self.room, 'location': self.location, 'online_url': self.online_url,
                'status': self.status, 'cancel_reason': self.cancel_reason}

    def to_dict(self):
        return {**self.public_dict(), 'course_id': self.course_id, 'module_id': self.module_id,
                'instructor_id': self.instructor_id, 'notes': self.notes,
                'attendance_from': iso(self.starts_at - ATTENDANCE_LEAD),
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

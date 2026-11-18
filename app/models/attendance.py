from app.extensions import db
from app.models.common import iso, utcnow

#: Anwesenheits-Status je Termin und Kandidat.
STATUSES = ('PRESENT', 'LATE', 'EXCUSED', 'ABSENT')


class Attendance(db.Model):
    """Anwesenheit EINES Kandidaten bei EINEM Termin (hoechstens ein Eintrag je Paar).

    Korrekturen aendern den Eintrag (Protokoll mit Alt/Neu im Verlauf).
    `note` ist intern und wird Kandidaten nicht angezeigt.
    """
    __tablename__ = 'attendance'
    __table_args__ = (db.UniqueConstraint('session_id', 'trainee_id', name='uq_attendance_session_trainee'),)

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('course_session.id'), nullable=False, index=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    minutes_late = db.Column(db.Integer, nullable=True)
    note = db.Column(db.String(500), nullable=True)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    recorded_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {'id': self.id, 'session_id': self.session_id, 'trainee_id': self.trainee_id,
                'status': self.status, 'minutes_late': self.minutes_late, 'note': self.note,
                'recorded_at': iso(self.recorded_at), 'recorded_by': self.recorded_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

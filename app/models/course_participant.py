from app.extensions import db
from app.models.common import iso, utcnow


class CourseParticipant(db.Model):
    """Ein Kandidat in einem Kurs (ein Kandidat kann in mehreren Kursen sein)."""
    __tablename__ = 'course_participant'

    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), primary_key=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), primary_key=True, index=True)
    added_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    added_by = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {'course_id': self.course_id, 'trainee_id': self.trainee_id,
                'added_at': iso(self.added_at), 'added_by': self.added_by}

from app.extensions import db
from app.models.common import iso, utcnow


class CourseModule(db.Model):
    """Ein Modul eines Curriculums, z.B. „Modul 8 – Konjunktiv II".

    Das Sprachniveau ist das des Curriculums (keine Doppelhaltung).
    `learning_objectives` ist die geordnete Liste der Lernziele (Texte).
    """
    __tablename__ = 'course_module'

    id = db.Column(db.Integer, primary_key=True)
    curriculum_id = db.Column(db.Integer, db.ForeignKey('curriculum.id'), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    duration_hours = db.Column(db.Numeric(6, 1), nullable=True)   # Unterrichtsstunden
    learning_objectives = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(20), nullable=False, default='DRAFT')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    curriculum = db.relationship('Curriculum', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'curriculum_id': self.curriculum_id, 'name': self.name,
                'description': self.description, 'position': self.position,
                'duration_hours': float(self.duration_hours) if self.duration_hours is not None else None,
                'learning_objectives': list(self.learning_objectives or []), 'status': self.status,
                'level': self.curriculum.level.ref(), 'program': self.curriculum.program.name,
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

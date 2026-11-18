from app.extensions import db
from app.models.common import iso, utcnow

#: Status fuer Curricula und Module — Workflow-Zustaende mit festem Verhalten.
STATUSES = ('DRAFT', 'ACTIVE', 'ARCHIVED')


class Curriculum(db.Model):
    """Lehrplan eines Programms fuer GENAU ein Sprachniveau (Programm -> Niveau -> Curriculum)."""
    __tablename__ = 'curriculum'
    __table_args__ = (db.UniqueConstraint('program_id', 'level_id', name='uq_curriculum_program_level'),)

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=False, index=True)
    level_id = db.Column(db.Integer, db.ForeignKey('language_level.id'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='DRAFT')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    program = db.relationship('Program', lazy='joined')
    level = db.relationship('LanguageLevel', lazy='joined')

    def to_dict(self):
        return {'id': self.id, 'program_id': self.program_id, 'program': self.program.name,
                'level': self.level.ref(), 'description': self.description, 'status': self.status,
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

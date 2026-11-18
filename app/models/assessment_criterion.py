from app.extensions import db
from app.models.assessment_template import num


class AssessmentCriterion(db.Model):
    """Unterkategorie einer Bewertungskategorie, z.B. „Aussprache" unter „Sprechen"."""
    __tablename__ = 'assessment_criterion'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('assessment_category.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    max_score = db.Column(db.Numeric(6, 1), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    category = db.relationship('AssessmentCategory', back_populates='criteria')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'max_score': num(self.max_score), 'position': self.position}

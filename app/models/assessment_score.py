from app.extensions import db
from app.models.assessment_template import num


def _key(category_id, criterion_id):
    return ('criterion', criterion_id) if criterion_id else ('category', category_id)


class AssessmentScore(db.Model):
    """Punkte einer Bewertung fuer GENAU ein bepunktbares Feld der Vorlage:
    eine Kategorie ohne Unterkategorien ODER eine Unterkategorie."""
    __tablename__ = 'assessment_score'
    __table_args__ = (
        db.UniqueConstraint('assessment_id', 'category_id', name='uq_assessment_score_category'),
        db.UniqueConstraint('assessment_id', 'criterion_id', name='uq_assessment_score_criterion'),
    )

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id', ondelete='CASCADE'),
                              nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('assessment_category.id'), nullable=True)
    criterion_id = db.Column(db.Integer, db.ForeignKey('assessment_criterion.id'), nullable=True)
    points = db.Column(db.Numeric(6, 1), nullable=False)

    def key(self):
        return _key(self.category_id, self.criterion_id)

    @classmethod
    def points_of(cls, assessment_ids):
        """{assessment_id: {key: Punkte}} fuer viele Bewertungen — eine schlanke Query statt Objekten
        (wie `Assessment.points()`, fuer Auswertungen ueber tausende Bewertungen)."""
        result = {aid: {} for aid in assessment_ids}
        if result:
            for aid, category_id, criterion_id, points in (
                    db.session.query(cls.assessment_id, cls.category_id, cls.criterion_id, cls.points)
                    .filter(cls.assessment_id.in_(list(result)))):
                result[aid][_key(category_id, criterion_id)] = points
        return result

    def to_dict(self):
        return {'category_id': self.category_id, 'criterion_id': self.criterion_id, 'points': num(self.points)}

from app.extensions import db
from app.models.assessment_template import num

#: Fertigkeiten fuer den Fortschritt (`app/services/progress.py`). Eine Kategorie
#: zaehlt zu hoechstens einer Fertigkeit; mehrere Kategorien duerfen dieselbe haben
#: (z.B. „Antwortformel" und „Aussprache" -> SPEAKING). Anzeige-Namen: i18n `sk_<CODE>`.
SKILLS = {'READING': 'Lesen', 'LISTENING': 'Hören', 'WRITING': 'Schreiben', 'SPEAKING': 'Sprechen',
          'GRAMMAR': 'Grammatik', 'VOCABULARY': 'Wortschatz'}


def skill_for_name(name):
    """Vorschlag aus dem Kategorienamen („Hören" -> LISTENING), sonst None."""
    wanted = (name or '').strip().lower()
    return next((code for code, label in SKILLS.items() if label.lower() == wanted), None)


class AssessmentCategory(db.Model):
    """Kategorie einer Bewertungsvorlage, z.B. „Sprechen".

    Ohne Unterkategorien wird die Kategorie direkt bepunktet; mit
    Unterkategorien ist ihre Punktzahl deren Summe, und `max_score` ist die
    Summe ihrer Hoechstpunkte (geprueft in `app/services/assessment_templates.py`).
    `passing_score` (optional) ist die Mindestpunktzahl dieser Kategorie.
    """
    __tablename__ = 'assessment_category'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('assessment_template.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    max_score = db.Column(db.Numeric(6, 1), nullable=False)
    weight = db.Column(db.Numeric(6, 2), nullable=False)
    passing_score = db.Column(db.Numeric(6, 1), nullable=True)
    skill = db.Column(db.String(20), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    template = db.relationship('AssessmentTemplate', back_populates='categories')
    criteria = db.relationship('AssessmentCriterion', lazy='selectin', cascade='all, delete-orphan',
                               order_by='AssessmentCriterion.position', back_populates='category')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'description': self.description,
                'max_score': num(self.max_score), 'weight': num(self.weight),
                'passing_score': num(self.passing_score), 'skill': self.skill, 'position': self.position,
                'criteria': [c.to_dict() for c in self.criteria]}

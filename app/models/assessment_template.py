from app.extensions import db
from app.models.common import iso, utcnow


def num(value):
    """Numeric-Spalte (Decimal) -> float fuer JSON (oder None)."""
    return None if value is None else float(value)


#: Vorschlag fuer neue Vorlagen (die Oberflaeche liest ihn aus GET /api/assessment-templates).
DEFAULT_PASSING_PERCENT = 60


class AssessmentTemplate(db.Model):
    """Bewertungsvorlage, z.B. „B1 Monatsbewertung": gewichtete Kategorien
    (optional mit Unterkategorien) und die Bestehensgrenze.

    Sobald eine Bewertung die Vorlage nutzt, ist ihre STRUKTUR gesperrt
    (Kategorien, Punkte, Gewichte, Grenzen) — alte Ergebnisse aendern sich so
    nie nachtraeglich. Aenderungen laufen ueber „Als neue Version kopieren".
    Berechnet wird ausschliesslich in `app/services/scoring.py`.
    """
    __tablename__ = 'assessment_template'
    # Name eindeutig nur unter den aktiven Vorlagen (Migration 0009)
    __table_args__ = (db.Index('uq_assessment_template_name_active', db.text('lower(name)'), unique=True,
                               postgresql_where=db.text('archived_at IS NULL')),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    level_id = db.Column(db.Integer, db.ForeignKey('language_level.id'), nullable=True)
    passing_percent = db.Column(db.Numeric(5, 1), nullable=False, default=DEFAULT_PASSING_PERCENT)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_by = db.Column(db.String(120), nullable=True)

    level = db.relationship('LanguageLevel', lazy='joined')
    categories = db.relationship('AssessmentCategory', lazy='selectin', cascade='all, delete-orphan',
                                 order_by='AssessmentCategory.position', back_populates='template')

    @property
    def is_archived(self):
        return self.archived_at is not None

    def ref(self):
        return {'id': self.id, 'name': self.name, 'archived': self.is_archived}

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'description': self.description,
                'level_id': self.level_id, 'level': self.level.ref() if self.level else None,
                'passing_percent': num(self.passing_percent),
                'categories': [c.to_dict() for c in self.categories],
                'max_total': num(sum(c.max_score for c in self.categories)),
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by,
                'archived_at': iso(self.archived_at), 'archived_by': self.archived_by}

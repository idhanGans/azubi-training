from app.extensions import db
from app.models.common import iso, utcnow


class LeiterRating(db.Model):
    """ALTBESTAND: fruehere Leiter-/Mitarbeiter-Bewertung (Sprache/Technik/Einstellung 1..10 + Notiz).

    Seit Migration 0020 ersetzt durch `staff_rating` (SPV/Leiter/Intern, `app/models/staff_rating.py`); die
    Tabelle bleibt unveraendert stehen (beim Umstieg 0 Zeilen auf prod und release), die App liest und
    schreibt sie nicht mehr. Erst entfernen, wenn sicher kein Bestand mehr gebraucht wird.
    """
    __tablename__ = 'leiter_rating'

    id = db.Column(db.Integer, primary_key=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    rater = db.Column(db.String(120), nullable=True)       # MSH-Login des Bewerters
    period = db.Column(db.String(12), nullable=True)
    r_language = db.Column(db.Integer, nullable=True)      # 1..10
    r_technical = db.Column(db.Integer, nullable=True)     # 1..10
    r_attitude = db.Column(db.Integer, nullable=True)      # 1..10 (Einstellung/Disziplin)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)   # Bearbeiter: der Bewerter

    def to_dict(self):
        return {
            'id': self.id, 'trainee_id': self.trainee_id, 'rater': self.rater,
            'period': self.period, 'r_language': self.r_language,
            'r_technical': self.r_technical, 'r_attitude': self.r_attitude,
            'note': self.note, 'created_at': iso(self.created_at), 'updated_at': iso(self.updated_at),
        }

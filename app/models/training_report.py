from datetime import timedelta

from app.extensions import db
from app.models.common import iso, utcnow

#: Wie lange nach dem Absenden ein Teilnehmer seinen eigenen Report noch
#: bearbeiten darf. Danach ist der Report gesperrt (nur noch Team sieht ihn).
REPORT_EDIT_WINDOW = timedelta(days=7)


class TrainingReport(db.Model):
    """Taeglicher Selbst-Report eines Teilnehmers: Trainingszeit + Gelerntes."""
    __tablename__ = 'training_report'

    id = db.Column(db.Integer, primary_key=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    period = db.Column(db.String(12), nullable=True)        # Tag im Format 'YYYY-MM-DD'
    hours = db.Column(db.Float, nullable=True)              # Trainingsstunden an dem Tag
    lang = db.Column(db.Boolean, nullable=False, default=False)   # Bereich Sprache?
    tech = db.Column(db.Boolean, nullable=False, default=False)   # Bereich Technik?
    learned = db.Column(db.Text, nullable=True)
    station = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)   # Bearbeiter: der Kandidat

    def is_editable(self, now=None):
        """Darf der Teilnehmer diesen Report noch aendern? (innerhalb 7 Tage)."""
        if self.created_at is None:
            return False
        return (now or utcnow()) - self.created_at <= REPORT_EDIT_WINDOW

    def to_dict(self):
        return {
            'id': self.id, 'trainee_id': self.trainee_id, 'period': self.period,
            'hours': self.hours, 'lang': self.lang, 'tech': self.tech,
            'learned': self.learned, 'station': self.station,
            'created_at': iso(self.created_at), 'updated_at': iso(self.updated_at), 'editable': self.is_editable(),
        }

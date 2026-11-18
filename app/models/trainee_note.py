from app.extensions import db
from app.models.common import utcnow


class TraineeNote(db.Model):
    """Freie Review-Notiz je Azubi an einem festen 2-Wochen-Stichtag der Gesamtbewertung
    (`app/services/review_notes.py`). Schreiben nur `note.edit` (Super-Admin), lesen jeder, der die
    Rangliste sieht. Genau eine Zeile je (Azubi, Stichtag); leerer Text loescht die Zeile."""
    __tablename__ = 'trainee_note'

    id = db.Column(db.Integer, primary_key=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    checkpoint = db.Column(db.Date, nullable=False)       # fester Stichtag aus review_notes.checkpoints()
    text = db.Column(db.String(2000), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    __table_args__ = (db.UniqueConstraint('trainee_id', 'checkpoint', name='uq_trainee_note'),)

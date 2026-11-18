from app.extensions import db
from app.models.common import iso, utcnow
from app.services import lesson_scoring


class LessonRating(db.Model):
    """Modul-Bewertung EINES anwesenden Teilnehmers fuer EIN Modul (+ Einheit) bei EINEM Termin
    (Panduan Penilaian Deutschkurs). Ein Termin kann mehrere Module abdecken — je Modul/Einheit eine Zeile.

    Punkte und Level werden nie gespeichert, sondern immer aus den Sternen berechnet (`lesson_scoring`).
    Leere Werte sind erlaubt (ignoriert, dann ohne Gesamt). `ha` leer = an dem Tag keine Hausaufgabe (zaehlt volle
    Punkte). Staerke/Ziel: ein oder mehrere Codes, gespeichert als „V,R" in fester Reihenfolge. `note` ist intern —
    Kandidaten sehen Sterne, Punkte, Level, Staerke und Ziel, nie die Notiz.
    """
    __tablename__ = 'lesson_rating'
    __table_args__ = (db.UniqueConstraint('session_id', 'module_id', 'unit', 'trainee_id',
                                          name='uq_lesson_rating_sheet_trainee'),)

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('course_session.id'), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey('course_module.id'), nullable=False, index=True)
    unit = db.Column(db.SmallInteger, nullable=False)       # Einheit des Moduls (1, 2 …)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    v = db.Column(db.SmallInteger, nullable=True)           # Verstehen 1..3
    r = db.Column(db.SmallInteger, nullable=True)           # Redemittel 1..3
    w = db.Column(db.SmallInteger, nullable=True)           # Wortschatz 1..3
    f = db.Column(db.SmallInteger, nullable=True)           # Fluessigkeit 1..3
    p = db.Column(db.SmallInteger, nullable=True)           # Problemloesung 1..3
    pu = db.Column(db.SmallInteger, nullable=True)          # Puenktlichkeit 0..1
    mi = db.Column(db.SmallInteger, nullable=True)          # Mitarbeit 0..2
    ha = db.Column(db.SmallInteger, nullable=True)          # Hausaufgabe 0..2, leer = keine aufgegeben
    strength = db.Column(db.String(11), nullable=True)      # V R W F P L, mehrere als „V,R"
    target = db.Column(db.String(11), nullable=True)        # V R W F P L, mehrere als „V,R"
    note = db.Column(db.String(1000), nullable=True)        # intern
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    module = db.relationship('CourseModule', lazy='joined')

    VALUE_FIELDS = (*lesson_scoring.ASPECTS, 'pu', 'mi', 'ha', 'strength', 'target')
    CODE_FIELDS = ('strength', 'target')

    def values(self):
        """Werte wie in der API: Staerke/Ziel als Liste von Codes."""
        return {k: (codes_of(getattr(self, k)) if k in self.CODE_FIELDS else getattr(self, k))
                for k in self.VALUE_FIELDS}

    def public_dict(self):
        """Fuer den Kandidaten: ohne Notiz und ohne Team-Logins."""
        return {'id': self.id, 'session_id': self.session_id, 'trainee_id': self.trainee_id,
                'module': {'id': self.module.id, 'name': self.module.name}, 'unit': self.unit, **self.values(),
                'result': lesson_scoring.evaluate(self.values())}

    def to_dict(self):
        return {**self.public_dict(), 'note': self.note, 'created_at': iso(self.created_at),
                'created_by': self.created_by, 'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}


def codes_of(stored):
    """„V,R" -> ['V', 'R']; leer -> []."""
    return stored.split(',') if stored else []


def stored_codes(codes):
    """['R', 'V'] -> „V,R" (feste Reihenfolge wie `lesson_scoring.FEEDBACK_CODES`); keine -> None."""
    ordered = [c for c in lesson_scoring.FEEDBACK_CODES if c in codes]
    return ','.join(ordered) or None

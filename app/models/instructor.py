from app.extensions import db
from app.models.common import iso, utcnow
from app.models.language_level import LanguageLevel

#: Einsatz-Status eines Dozenten. Nur AKTIVE Dozenten koennen Kursen neu
#: zugeordnet werden.
STATUSES = ('ACTIVE', 'ON_LEAVE', 'INACTIVE')

#: Welche Sprachniveaus ein Dozent unterrichtet (n:m).
instructor_level = db.Table(
    'instructor_level',
    db.Column('instructor_id', db.Integer, db.ForeignKey('instructor.id', ondelete='CASCADE'), primary_key=True),
    db.Column('level_id', db.Integer, db.ForeignKey('language_level.id'), primary_key=True),
)


class Instructor(db.Model):
    """Ein Dozent des Sprachkurses.

    `msh_user` verknuepft den MSH-Login: wer hier eingetragen ist, sieht unter
    „Mein Unterricht" seine Kurse und (ohne `candidate.view_all`) nur deren
    Teilnehmer. Die Rolle DOZENT (Rechte) vergibt die Benutzerverwaltung.
    `availability` ist die Wochen-Verfuegbarkeit: je Wochentag hoechstens ein
    Zeitfenster `{weekday: 0=Mo…6=So, start: 'HH:MM', end: 'HH:MM'}`.
    """
    __tablename__ = 'instructor'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    msh_user = db.Column(db.String(120), nullable=True, unique=True)
    qualification = db.Column(db.Text, nullable=True)
    specialization = db.Column(db.String(200), nullable=True)
    availability = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(20), nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_by = db.Column(db.String(120), nullable=True)

    levels = db.relationship('LanguageLevel', secondary=instructor_level, lazy='selectin',
                             order_by=LanguageLevel.sort_order)

    @property
    def is_archived(self):
        return self.archived_at is not None

    def teaches(self, level_id):
        return any(level.id == level_id for level in self.levels)

    def ref(self):
        return {'id': self.id, 'name': self.name, 'status': self.status, 'archived': self.is_archived}

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'email': self.email, 'msh_user': self.msh_user,
                'qualification': self.qualification, 'specialization': self.specialization,
                'levels': [level.ref() for level in self.levels],
                'availability': list(self.availability or []), 'status': self.status,
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by,
                'archived_at': iso(self.archived_at), 'archived_by': self.archived_by}

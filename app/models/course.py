from app.extensions import db
from app.models.common import iso, utcnow

#: Kurs-Status (Workflow mit festem Verhalten, daher kein Stammdaten-Katalog).
STATUSES = ('PLANNED', 'RUNNING', 'COMPLETED')
#: Deutsche Bezeichnung fuer Berichte/CSV (die Oberflaeche uebersetzt selbst ueber `cs_<STATUS>`).
STATUS_LABELS = {'PLANNED': 'Geplant', 'RUNNING': 'Laufend', 'COMPLETED': 'Abgeschlossen'}


class Course(db.Model):
    """Ein Kurs (Klasse): Gruppe von Kandidaten auf einem Sprachniveau, mit
    aktuellem Modul und zugeordnetem Dozenten. Termine haengen spaeter am Kurs.

    Das Modul muss zum Sprachniveau des Kurses gehoeren; der Dozent muss aktiv
    sein und das Niveau unterrichten (`app/services/courses.py`).
    Archivieren statt Loeschen; der Name ist unter den nicht archivierten
    Kursen eindeutig (Index in Migration 0006).
    """
    __tablename__ = 'course'
    # Name eindeutig nur unter den nicht archivierten Kursen (Migration 0006)
    __table_args__ = (db.Index('uq_course_name_active', db.text('lower(name)'), unique=True,
                               postgresql_where=db.text('archived_at IS NULL')),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    level_id = db.Column(db.Integer, db.ForeignKey('language_level.id'), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey('course_module.id'), nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('instructor.id'), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='PLANNED')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_by = db.Column(db.String(120), nullable=True)

    level = db.relationship('LanguageLevel', lazy='joined')
    module = db.relationship('CourseModule', lazy='joined')
    instructor = db.relationship('Instructor', lazy='joined')

    @property
    def is_archived(self):
        return self.archived_at is not None

    def to_dict(self):
        module = self.module
        return {'id': self.id, 'name': self.name, 'description': self.description,
                'level_id': self.level_id, 'level': self.level.ref(),
                'module_id': self.module_id,
                'module': {'id': module.id, 'name': module.name, 'program': module.curriculum.program.name}
                if module else None,
                'instructor_id': self.instructor_id,
                'instructor': self.instructor.ref() if self.instructor else None,
                'status': self.status,
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by,
                'archived_at': iso(self.archived_at), 'archived_by': self.archived_by}

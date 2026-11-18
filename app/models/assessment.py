from app.extensions import db
from app.models.assessment_template import num
from app.models.common import iso, utcnow

#: DRAFT = Entwurf (nur intern, Punkte duerfen fehlen), FINAL = abgeschlossen
#: (alle Punkte da, Ergebnis gespeichert, fuer den Kandidaten sichtbar).
STATUSES = ('DRAFT', 'FINAL')

#: Feedback fuer den Kandidaten — sichtbar in „Meine Bewertungen".
FEEDBACK_FIELDS = ('strengths', 'improvements', 'recommendations', 'general_feedback')


class Assessment(db.Model):
    """Eine Bewertung: Kandidat + Vorlage + Pruefer (Dozent) + Datum.

    `overall_percent`/`passed` schreibt NUR `app/services/scoring.py` (beim
    Abschliessen und bei Korrekturen); bei Entwuerfen sind sie leer.
    `internal_note` ist intern und steht NIE in `public_dict()`.
    """
    __tablename__ = 'assessment'
    __table_args__ = (db.Index('ix_assessment_assessed_on', 'assessed_on', 'id'),)   # Liste: neueste zuerst

    id = db.Column(db.Integer, primary_key=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('assessment_template.id'), nullable=False, index=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('instructor.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True, index=True)
    assessed_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False, default='DRAFT')
    overall_percent = db.Column(db.Numeric(5, 1), nullable=True)
    passed = db.Column(db.Boolean, nullable=True)
    strengths = db.Column(db.Text, nullable=True)
    improvements = db.Column(db.Text, nullable=True)
    recommendations = db.Column(db.Text, nullable=True)
    general_feedback = db.Column(db.Text, nullable=True)
    internal_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    finalized_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finalized_by = db.Column(db.String(120), nullable=True)

    trainee = db.relationship('Trainee', lazy='joined')
    template = db.relationship('AssessmentTemplate', lazy='joined')
    instructor = db.relationship('Instructor', lazy='joined')
    course = db.relationship('Course', lazy='joined')
    scores = db.relationship('AssessmentScore', lazy='selectin', cascade='all, delete-orphan')

    def points(self):
        """{('category'|'criterion', id): Decimal} — Eingabe fuer `scoring.evaluate`."""
        return {s.key(): s.points for s in self.scores}

    def summary(self):
        """Kurzform fuer Listen und den Verlauf (intern)."""
        t = self.trainee
        return {'id': self.id, 'assessed_on': self.assessed_on.isoformat(), 'status': self.status,
                'overall_percent': num(self.overall_percent), 'passed': self.passed,
                'trainee': {'id': t.id, 'candidate_no': t.candidate_no, 'name': t.name, 'archived': t.is_archived},
                'template': self.template.ref(), 'instructor': self.instructor.ref(),
                'course': {'id': self.course.id, 'name': self.course.name} if self.course else None,
                'finalized_at': iso(self.finalized_at)}

    def to_dict(self):
        """Vollstaendig fuer interne Nutzer — inkl. interner Notiz."""
        return {**self.summary(), **{f: getattr(self, f) for f in FEEDBACK_FIELDS},
                'internal_note': self.internal_note,
                'scores': [s.to_dict() for s in self.scores],
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by,
                'finalized_by': self.finalized_by}

    def public_dict(self):
        """Fuer den Kandidaten selbst: Ergebnis + Feedback, OHNE interne Notiz und Bearbeiter-Logins."""
        return {'id': self.id, 'assessed_on': self.assessed_on.isoformat(),
                'overall_percent': num(self.overall_percent), 'passed': self.passed,
                'template': {'id': self.template.id, 'name': self.template.name},
                'instructor': {'name': self.instructor.name},
                'course': {'name': self.course.name} if self.course else None,
                **{f: getattr(self, f) for f in FEEDBACK_FIELDS}}

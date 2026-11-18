from sqlalchemy import FetchedValue

from app.extensions import db
from app.models.common import iso, utcnow


def _day(value):
    return value.isoformat() if value else None


class Trainee(db.Model):
    """A candidate (Kandidat, participant/Teilnehmer) of the program.

    `msh_user` links the MSH login to this record: whoever is entered here
    has the role CANDIDATE in the app and sees only themself. Archiving
    replaces deletion — the history (Verlauf) is preserved, the candidate
    only loses access. `candidate_no` is assigned by the DB (sequence,
    format K-00001).
    """
    __tablename__ = 'trainee'
    # as in migration 0001: UNIQUE constraint plus its own (non-unique) index
    __table_args__ = (db.Index('ix_trainee_msh_user', 'msh_user'),)

    id = db.Column(db.Integer, primary_key=True)
    candidate_no = db.Column(db.String(20), nullable=False, unique=True, server_default=FetchedValue())
    name = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    fach = db.Column(db.String(20), nullable=True)          # 'Elektro' | 'SHK' | None
    abteilung = db.Column(db.String(80), nullable=True)     # placement, e.g. 'Berlin – PV-Assistent'
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True, index=True)  # team
    supervisor = db.Column(db.String(120), nullable=True, index=True)   # MSH login of the SPV (supervisor)
    target_occupation = db.Column(db.String(120), nullable=True)   # target occupation (Ausbildungsberuf)
    program_id = db.Column(db.Integer, db.ForeignKey('program.id'), nullable=True, index=True)
    status_id = db.Column(db.Integer, db.ForeignKey('candidate_status.id'), nullable=True, index=True)
    current_level_id = db.Column(db.Integer, db.ForeignKey('language_level.id'), nullable=True, index=True)
    target_level_id = db.Column(db.Integer, db.ForeignKey('language_level.id'), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    expected_completion_date = db.Column(db.Date, nullable=True)
    msh_user = db.Column(db.String(120), nullable=True, unique=True)  # MSH login
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_by = db.Column(db.String(120), nullable=True)

    program = db.relationship('Program', lazy='joined')
    status = db.relationship('CandidateStatus', lazy='joined')
    current_level = db.relationship('LanguageLevel', foreign_keys=[current_level_id], lazy='joined')
    target_level = db.relationship('LanguageLevel', foreign_keys=[target_level_id], lazy='joined')
    department = db.relationship('Department', lazy='joined')

    @property
    def is_archived(self):
        return self.archived_at is not None

    def to_dict(self):
        return {
            'id': self.id, 'candidate_no': self.candidate_no, 'name': self.name,
            'nickname': self.nickname, 'email': self.email, 'phone': self.phone,
            'date_of_birth': _day(self.date_of_birth), 'fach': self.fach,
            'abteilung': self.abteilung, 'target_occupation': self.target_occupation,
            'department_id': self.department_id, 'department': self.department.ref() if self.department else None,
            'supervisor': self.supervisor,
            'program_id': self.program_id,
            'program': {'id': self.program.id, 'name': self.program.name} if self.program else None,
            'status_id': self.status_id, 'current_level_id': self.current_level_id,
            'target_level_id': self.target_level_id,
            'status': self.status.ref() if self.status else None,
            'current_level': self.current_level.ref() if self.current_level else None,
            'target_level': self.target_level.ref() if self.target_level else None,
            'start_date': _day(self.start_date),
            'expected_completion_date': _day(self.expected_completion_date),
            'msh_user': self.msh_user, 'active': self.active,
            'created_at': iso(self.created_at), 'created_by': self.created_by,
            'updated_at': iso(self.updated_at), 'updated_by': self.updated_by,
            'archived_at': iso(self.archived_at), 'archived_by': self.archived_by,
        }

    #: Fields the candidate does NOT see themself: who created/changed/archived them (team logins).
    _INTERNAL = ('created_by', 'updated_by', 'archived_by', 'archived_at', 'active', 'supervisor')

    def public_dict(self):
        """Own master data for the candidate portal (without team logins)."""
        return {k: v for k, v in self.to_dict().items() if k not in self._INTERNAL}

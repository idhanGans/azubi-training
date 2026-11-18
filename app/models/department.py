from app.extensions import db
from app.models.common import iso, utcnow


class Department(db.Model):
    """Abteilung (Team) eines Kandidaten, z.B. „Erkelenz" oder „Wärmepumpe" — Grundlage fuer die Leiter-Sicht und
    die Rangliste je Abteilung. Die genaue Stelle („Erkelenz – PV-Assistent") bleibt im Freitext `trainee.abteilung`.
    Nie loeschen, nur deaktivieren (Kandidaten und Bewertungen haengen daran)."""
    __tablename__ = 'department'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    leaders = db.relationship('DepartmentLeader', lazy='select', order_by='DepartmentLeader.username',
                              cascade='all, delete-orphan')

    def ref(self):
        return {'id': self.id, 'name': self.name}

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'active': self.active,
                'leaders': [x.username for x in self.leaders],
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

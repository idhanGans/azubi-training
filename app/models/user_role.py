from app.extensions import db
from app.models.common import iso, utcnow


class UserRole(db.Model):
    """Eine Team-Rolle fuer einen MSH-Login (ein Login kann mehrere haben).

    Die Rolle KANDIDAT steht hier nie: Kandidat ist, wessen Login an einem
    Teilnehmer haengt (`trainee.msh_user`). Welche Rolle was darf, legt
    `app/services/permissions.py` fest.
    """
    __tablename__ = 'user_role'
    __table_args__ = (db.UniqueConstraint('username', 'role', name='uq_user_role_username_role'),)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), nullable=False, index=True)   # immer klein geschrieben
    role = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username, 'role': self.role,
            'created_at': iso(self.created_at), 'created_by': self.created_by,
        }

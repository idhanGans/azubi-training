from app.extensions import db
from app.models.common import iso, utcnow


class Program(db.Model):
    """Ein Programm, z.B. „Deutschsprachkurs". Die enthaltenen Sprachniveaus
    ergeben sich aus seinen Curricula (je Niveau genau eines)."""
    __tablename__ = 'program'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'description': self.description,
                'active': self.active, 'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

"""Gemeinsame Form der konfigurierbaren Stammdaten-Listen (Kandidaten-Status, Sprachniveaus).

Beide haben dieselbe Form; gepflegt werden sie in /settings (system.manage).
Eintraege werden nie geloescht, nur deaktiviert — Kandidaten verweisen darauf.
"""
from app.extensions import db
from app.models.common import iso, utcnow


class CatalogMixin:
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {'id': self.id, 'code': self.code, 'name': self.name,
                'sort_order': self.sort_order, 'active': self.active,
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by}

    def ref(self):
        """Kurzform fuer Listen/Profile."""
        return {'id': self.id, 'code': self.code, 'name': self.name}


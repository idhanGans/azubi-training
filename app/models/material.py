from app.extensions import db
from app.models.common import iso, utcnow

#: Material-Arten. Datei = hochgeladene Datei, Link = externe URL.
TYPES = ('PDF', 'VIDEO', 'DOCUMENT', 'LINK', 'IMAGE', 'EXERCISE', 'HOMEWORK')
FILE_REQUIRED = ('PDF', 'DOCUMENT', 'IMAGE')
URL_REQUIRED = ('LINK',)


class Material(db.Model):
    """Lernmaterial eines Moduls: Link ODER hochgeladene Datei (nie beides).

    Dateien liegen im File-Store (`app/services/file_store.py`) unter einem
    zufaelligen `storage_key`; ausgeliefert werden sie nur ueber die Route mit
    Rechte-Pruefung, nie direkt. Archivieren statt Loeschen.
    """
    __tablename__ = 'material'

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('course_module.id'), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(1000), nullable=True)
    storage_key = db.Column(db.String(64), nullable=True, unique=True)
    file_name = db.Column(db.String(255), nullable=True)
    content_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.BigInteger, nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    team_only = db.Column(db.Boolean, nullable=False, default=False)   # nur Team/Dozenten, nie Kandidaten
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)
    archived_by = db.Column(db.String(120), nullable=True)

    @property
    def has_file(self):
        return self.storage_key is not None

    def to_dict(self):
        return {'id': self.id, 'module_id': self.module_id, 'type': self.type, 'title': self.title,
                'description': self.description, 'url': self.url, 'has_file': self.has_file,
                'file_name': self.file_name, 'content_type': self.content_type,
                'size_bytes': self.size_bytes, 'position': self.position, 'team_only': self.team_only,
                'created_at': iso(self.created_at), 'created_by': self.created_by,
                'updated_at': iso(self.updated_at), 'updated_by': self.updated_by,
                'archived_at': iso(self.archived_at), 'archived_by': self.archived_by}

    def public_dict(self):
        """Fuer Kandidaten: Inhalt + Datei-Infos, ohne Team-Logins und Speicher-Schluessel
        (Material mit `team_only` bekommen Kandidaten gar nicht — `services/portal.py`)."""
        return {'id': self.id, 'type': self.type, 'title': self.title, 'description': self.description,
                'url': self.url, 'has_file': self.has_file, 'file_name': self.file_name,
                'size_bytes': self.size_bytes}

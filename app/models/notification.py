from app.extensions import db
from app.models.common import iso, utcnow

#: Arten — der Text entsteht in der Oberflaeche aus `nt_<TYPE>` + `params` (DE/EN/ID).
TYPES = ('SESSION_REMINDER', 'SESSION_CANCELLED', 'SESSION_MOVED', 'COURSE_JOINED', 'ASSESSMENT_PUBLISHED',
         'ASSESSMENT_CORRECTED', 'ASSESSMENT_DRAFT_OPEN', 'ATTENDANCE_MISSING')


class Notification(db.Model):
    """In-App-Benachrichtigung fuer EINEN Login (`recipient`).

    `read_at` leer = ungelesen. `dedupe_key` verhindert Doppelte (UNIQUE je
    Empfaenger), z.B. die Erinnerung an denselben Termin. `params` sind die
    Platzhalter fuer den Text; `link` fuehrt zur passenden Seite.
    """
    __tablename__ = 'notification'
    __table_args__ = (db.UniqueConstraint('recipient', 'dedupe_key', name='uq_notification_recipient_key'),
                      db.Index('ix_notification_recipient_unread', 'recipient', 'read_at'))

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False)
    params = db.Column(db.JSON, nullable=False, default=dict)
    link = db.Column(db.String(300), nullable=True)
    dedupe_key = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {'id': self.id, 'type': self.type, 'params': dict(self.params or {}), 'link': self.link,
                'created_at': iso(self.created_at), 'read': self.read_at is not None, 'read_at': iso(self.read_at)}

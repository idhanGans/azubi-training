from app.extensions import db
from app.models.common import iso, utcnow
from app.services import local_time

#: Who rates: the assigned SPV, a leader of the department (both count as "SPV feedback")
#: or the internal team (`rating.internal`, "Internes Team").
KINDS = ('SPV', 'LEITER', 'INTERN')
CATEGORIES = ('r_practical', 'r_reliability', 'r_motivation')


class StaffRating(db.Model):
    """Rating of a candidate by SPV, leader or internal team for ONE program month — 1..10 each for practical
    performance, reliability and motivation & behaviour + note. Basis of the parts "SPV" and "Intern" of the
    overall rating (`app/services/overall.py`). One rating per candidate, rater and month; the rater may
    correct their own rating on the same day (school local time), after that it is fixed."""
    __tablename__ = 'staff_rating'
    __table_args__ = (db.UniqueConstraint('trainee_id', 'rater', 'month', name='uq_staff_rating_month'),)

    id = db.Column(db.Integer, primary_key=True)
    trainee_id = db.Column(db.Integer, db.ForeignKey('trainee.id'), nullable=False, index=True)
    rater = db.Column(db.String(120), nullable=False, index=True)       # MSH login of the rater
    kind = db.Column(db.String(10), nullable=False)                     # KINDS — fixed when submitted
    month = db.Column(db.SmallInteger, nullable=False)                  # program month 1..3
    r_practical = db.Column(db.SmallInteger, nullable=False)            # practical performance 1..10
    r_reliability = db.Column(db.SmallInteger, nullable=False)          # reliability 1..10
    r_motivation = db.Column(db.SmallInteger, nullable=False)           # motivation & behaviour 1..10
    note = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=utcnow)
    updated_by = db.Column(db.String(120), nullable=True)

    def is_editable_by(self, login):
        """Own rating, submitted on the same day?"""
        return (self.rater == login and self.created_at is not None
                and local_time.local_parts(self.created_at)[0] == local_time.today().isoformat())

    def scores(self):
        return {k: getattr(self, k) for k in CATEGORIES}

    def to_dict(self):
        return {'id': self.id, 'trainee_id': self.trainee_id, 'rater': self.rater, 'kind': self.kind,
                'month': self.month, **self.scores(), 'note': self.note, 'created_at': iso(self.created_at),
                'updated_at': iso(self.updated_at)}

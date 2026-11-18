from app.extensions import db
from app.models.common import utcnow


class DepartmentLeader(db.Model):
    """Leiter einer Abteilung (MSH-Login): sieht und bewertet ALLE aktiven Kandidaten dieser Abteilung.
    Eine Abteilung kann mehrere Leiter haben, ein Login mehrere Abteilungen leiten."""
    __tablename__ = 'department_leader'
    __table_args__ = (db.UniqueConstraint('department_id', 'username', name='uq_department_leader'),)

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    username = db.Column(db.String(120), nullable=False, index=True)    # immer klein geschrieben
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    created_by = db.Column(db.String(120), nullable=True)

from app.extensions import db
from app.models.catalog import CatalogMixin


class CandidateStatus(CatalogMixin, db.Model):
    """Wo steht ein Kandidat? (Interessent, Im Sprachkurs, …)"""
    __tablename__ = 'candidate_status'

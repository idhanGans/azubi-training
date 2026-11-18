from app.extensions import db
from app.models.catalog import CatalogMixin


class LanguageLevel(CatalogMixin, db.Model):
    """Sprachniveau nach GER (A1 … C1); `sort_order` ist die Rangfolge."""
    __tablename__ = 'language_level'

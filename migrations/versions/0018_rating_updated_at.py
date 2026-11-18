"""Mitarbeiter-Bewertung korrigierbar: `leiter_rating.updated_at`

Der Bewerter darf seine eigene Bewertung am selben Tag aendern (Alt/Neu im Verlauf); `updated_at` zeigt,
dass sie korrigiert wurde. Bestand bleibt unveraendert (NULL = nie geaendert).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-05 10:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('leiter_rating', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('leiter_rating', 'updated_at')

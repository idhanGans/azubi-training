"""Index fuer die Bewertungsliste (neueste zuerst)

- ix_assessment_assessed_on (assessed_on, id): die Liste sortiert nach Datum + ID und
  zeigt seitenweise — ohne Index sortiert Postgres dafuer jedes Mal alle Bewertungen.

Nur ein Index — bestehende Daten bleiben unveraendert.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25 14:00:00
"""
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_assessment_assessed_on', 'assessment', ['assessed_on', 'id'])


def downgrade():
    op.drop_index('ix_assessment_assessed_on', table_name='assessment')

"""Lernmaterial nur fuer Lehrkraefte (Loesungen, Ablaufplaene, Musterantworten)

`material.team_only`: Kandidaten sehen solches Material weder in „Meine Module" noch koennen sie die Datei
laden; Team und Dozenten sehen es wie bisher. Bestand = fuer alle sichtbar (wie vorher).

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-26 13:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('material', sa.Column('team_only', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('material', 'team_only')

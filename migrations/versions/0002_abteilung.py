"""trainee.abteilung — Platzierung (z.B. 'Berlin – PV-Assistent')

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('trainee', sa.Column('abteilung', sa.String(length=80), nullable=True))


def downgrade():
    op.drop_column('trainee', 'abteilung')

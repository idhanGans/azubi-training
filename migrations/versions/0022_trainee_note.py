"""Review-Notizen der Gesamtbewertung: `trainee_note`

Freie Notiz je Azubi an festen 2-Wochen-Stichtagen (`app/services/review_notes.py`). Schreiben nur
`note.edit` (Super-Admin); genau eine Zeile je (Azubi, Stichtag).

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-19 12:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trainee_note',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trainee_id', sa.Integer(), sa.ForeignKey('trainee.id', name='fk_trainee_note_trainee'),
                  nullable=False),
        sa.Column('checkpoint', sa.Date(), nullable=False),
        sa.Column('text', sa.String(length=2000), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.UniqueConstraint('trainee_id', 'checkpoint', name='uq_trainee_note'),
    )
    op.create_index('ix_trainee_note_trainee_id', 'trainee_note', ['trainee_id'])


def downgrade():
    op.drop_table('trainee_note')

"""In-App-Benachrichtigungen

- notification: Empfaenger (Login), Art, Platzhalter (JSON), Link, gelesen am;
  UNIQUE (recipient, dedupe_key) gegen doppelte Erinnerungen

Nur eine neue Tabelle — bestehende Daten bleiben unberuehrt.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-25 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

TYPES = ('SESSION_REMINDER', 'SESSION_CANCELLED', 'SESSION_MOVED', 'COURSE_JOINED', 'ASSESSMENT_PUBLISHED',
         'ASSESSMENT_CORRECTED', 'ASSESSMENT_DRAFT_OPEN', 'ATTENDANCE_MISSING')


def upgrade():
    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('recipient', sa.String(length=120), nullable=False),
        sa.Column('type', sa.String(length=40), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('link', sa.String(length=300), nullable=True),
        sa.Column('dedupe_key', sa.String(length=160), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('recipient', 'dedupe_key', name='uq_notification_recipient_key'),
        sa.CheckConstraint('type IN (' + ', '.join(f"'{t}'" for t in TYPES) + ')', name='ck_notification_type'),
    )
    op.create_index('ix_notification_recipient_unread', 'notification', ['recipient', 'read_at'])
    op.create_index('ix_notification_recipient', 'notification', ['recipient'])


def downgrade():
    op.drop_table('notification')

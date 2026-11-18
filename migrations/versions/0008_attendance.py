"""Anwesenheit je Termin und Kandidat

- attendance: Status PRESENT|LATE|EXCUSED|ABSENT, Minuten zu spaet (nur bei
  LATE), interne Notiz; UNIQUE (session_id, trainee_id) — keine Doppel-Erfassung

Nur eine neue Tabelle — bestehende Daten bleiben unberuehrt.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'attendance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('course_session.id', name='fk_attendance_session'),
                  nullable=False),
        sa.Column('trainee_id', sa.Integer(), sa.ForeignKey('trainee.id', name='fk_attendance_trainee'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('minutes_late', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('recorded_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.UniqueConstraint('session_id', 'trainee_id', name='uq_attendance_session_trainee'),
        sa.CheckConstraint("status IN ('PRESENT', 'LATE', 'EXCUSED', 'ABSENT')", name='ck_attendance_status'),
        sa.CheckConstraint("minutes_late IS NULL OR (status = 'LATE' AND minutes_late BETWEEN 1 AND 600)",
                           name='ck_attendance_minutes_late'),
    )
    op.create_index('ix_attendance_session_id', 'attendance', ['session_id'])
    op.create_index('ix_attendance_trainee_id', 'attendance', ['trainee_id'])


def downgrade():
    op.drop_table('attendance')

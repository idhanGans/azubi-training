"""Terminplanung: Unterrichtstermine je Kurs

- course_session: Beginn/Ende als timestamptz (UTC), Raum, Ort, Online-Link,
  Status (SCHEDULED|COMPLETED|CANCELLED, abgesagt mit Grund), Notizen;
  Dozent + Modul je Termin (Vorgabe vom Kurs)

Nur eine neue Tabelle — bestehende Daten bleiben unberuehrt.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-24 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'course_session',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('course.id', name='fk_session_course'), nullable=False),
        sa.Column('module_id', sa.Integer(), sa.ForeignKey('course_module.id', name='fk_session_module'), nullable=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('instructor.id', name='fk_session_instructor'),
                  nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('room', sa.String(length=80), nullable=True),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('online_url', sa.String(length=1000), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='SCHEDULED'),
        sa.Column('cancel_reason', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.CheckConstraint("status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED')", name='ck_session_status'),
        sa.CheckConstraint('ends_at > starts_at', name='ck_session_end_after_start'),
        sa.CheckConstraint("status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name='ck_session_cancel_reason'),
    )
    op.create_index('ix_course_session_course_id', 'course_session', ['course_id'])
    op.create_index('ix_course_session_instructor_id', 'course_session', ['instructor_id'])
    op.create_index('ix_course_session_starts_at', 'course_session', ['starts_at'])


def downgrade():
    op.drop_table('course_session')

"""Dozenten und Kurse

- instructor: Stammdaten, Login-Verknuepfung (eindeutig), Wochen-Verfuegbarkeit
  (JSON), Status; instructor_level: welche Niveaus er unterrichtet
- course: Kurs/Klasse mit Niveau, aktuellem Modul, Dozent, Status;
  Name eindeutig unter den NICHT archivierten Kursen (Teil-Index)
- course_participant: Kandidaten eines Kurses

Nur neue Tabellen — bestehende Daten bleiben unberuehrt.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_by', sa.String(length=120), nullable=True),
    ]


def upgrade():
    op.create_table(
        'instructor',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('msh_user', sa.String(length=120), nullable=True),
        sa.Column('qualification', sa.Text(), nullable=True),
        sa.Column('specialization', sa.String(length=200), nullable=True),
        sa.Column('availability', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
        *_audit_columns(),
        sa.UniqueConstraint('msh_user', name='uq_instructor_msh_user'),
        sa.CheckConstraint("status IN ('ACTIVE', 'ON_LEAVE', 'INACTIVE')", name='ck_instructor_status'),
    )
    op.create_table(
        'instructor_level',
        sa.Column('instructor_id', sa.Integer(),
                  sa.ForeignKey('instructor.id', name='fk_instructor_level_instructor', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('level_id', sa.Integer(), sa.ForeignKey('language_level.id', name='fk_instructor_level_level'),
                  primary_key=True),
    )
    op.create_table(
        'course',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('level_id', sa.Integer(), sa.ForeignKey('language_level.id', name='fk_course_level'), nullable=False),
        sa.Column('module_id', sa.Integer(), sa.ForeignKey('course_module.id', name='fk_course_module'), nullable=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('instructor.id', name='fk_course_instructor'),
                  nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PLANNED'),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('PLANNED', 'RUNNING', 'COMPLETED')", name='ck_course_status'),
    )
    op.create_index('ix_course_level_id', 'course', ['level_id'])
    op.create_index('ix_course_instructor_id', 'course', ['instructor_id'])
    op.create_index('uq_course_name_active', 'course', [sa.text('lower(name)')], unique=True,
                    postgresql_where=sa.text('archived_at IS NULL'))
    op.create_table(
        'course_participant',
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('course.id', name='fk_course_participant_course'),
                  primary_key=True),
        sa.Column('trainee_id', sa.Integer(), sa.ForeignKey('trainee.id', name='fk_course_participant_trainee'),
                  primary_key=True),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('added_by', sa.String(length=120), nullable=True),
    )
    op.create_index('ix_course_participant_trainee_id', 'course_participant', ['trainee_id'])


def downgrade():
    op.drop_table('course_participant')
    op.drop_table('course')
    op.drop_table('instructor_level')
    op.drop_table('instructor')

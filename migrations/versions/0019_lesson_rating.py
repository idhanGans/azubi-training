"""Modul-Bewertung je Termin (Panduan Penilaian Deutschkurs): `lesson_rating`

Je Termin + anwesendem Teilnehmer: 5 Sprech-Aspekte (1–3 Sterne), Puenktlichkeit/Mitarbeit/Hausaufgabe,
Staerke + Ziel (Codes V R W F P L) und interne Notiz. Punkte/Level rechnet `services/lesson_scoring.py`.
Neue Tabelle, kein Bestand.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-08 10:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None

CODES = "('V', 'R', 'W', 'F', 'P', 'L')"


def upgrade():
    op.create_table(
        'lesson_rating',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('course_session.id', name='fk_lesson_rating_session'),
                  nullable=False),
        sa.Column('trainee_id', sa.Integer(), sa.ForeignKey('trainee.id', name='fk_lesson_rating_trainee'),
                  nullable=False),
        *(sa.Column(name, sa.SmallInteger(), nullable=False) for name in ('v', 'r', 'w', 'f', 'p', 'pu', 'mi')),
        sa.Column('ha', sa.SmallInteger(), nullable=True),
        sa.Column('strength', sa.String(length=1), nullable=False),
        sa.Column('target', sa.String(length=1), nullable=False),
        sa.Column('note', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.UniqueConstraint('session_id', 'trainee_id', name='uq_lesson_rating_session_trainee'),
        *(sa.CheckConstraint(f'{name} BETWEEN 1 AND 3', name=f'ck_lesson_rating_{name}')
          for name in ('v', 'r', 'w', 'f', 'p')),
        sa.CheckConstraint('pu BETWEEN 0 AND 1', name='ck_lesson_rating_pu'),
        sa.CheckConstraint('mi BETWEEN 0 AND 2', name='ck_lesson_rating_mi'),
        sa.CheckConstraint('ha IS NULL OR ha BETWEEN 0 AND 2', name='ck_lesson_rating_ha'),
        sa.CheckConstraint(f'strength IN {CODES}', name='ck_lesson_rating_strength'),
        sa.CheckConstraint(f'target IN {CODES}', name='ck_lesson_rating_target'),
    )
    op.create_index('ix_lesson_rating_session_id', 'lesson_rating', ['session_id'])
    op.create_index('ix_lesson_rating_trainee_id', 'lesson_rating', ['trainee_id'])


def downgrade():
    op.drop_table('lesson_rating')

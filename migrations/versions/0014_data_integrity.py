"""Datenintegritaet: Wer/wann an Stammdaten und Reports, Wertebereiche in der Datenbank

- candidate_status, language_level: created_by, updated_at, updated_by (Stammdaten werden
  umbenannt/deaktiviert — bisher stand nur im Verlauf, wer das war)
- training_report: updated_at (Kandidaten bearbeiten ihren Report bis zu 7 Tage lang)
- CHECK: Report-Stunden 0..24, Leiter-Bewertungen 1..10, Bewertungspunkte in 0,5er-Schritten —
  bisher nur in der Anwendung geprueft. Bestehende Daten erfuellen sie: der main-Stand hat
  Stunden auf 0..24 und Bewertungen auf 1..10 begrenzt, Punkte kamen immer ueber `half_points`.

Nur neue, leere Spalten und Pruefregeln — bestehende Daten bleiben unveraendert.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-25 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

CATALOGS = ('candidate_status', 'language_level')
CHECKS = [
    ('ck_training_report_hours', 'training_report', 'hours IS NULL OR (hours >= 0 AND hours <= 24)'),
    ('ck_leiter_rating_scores', 'leiter_rating',
     '(r_language IS NULL OR r_language BETWEEN 1 AND 10) AND (r_technical IS NULL OR r_technical BETWEEN 1 AND 10)'
     ' AND (r_attitude IS NULL OR r_attitude BETWEEN 1 AND 10)'),
    ('ck_assessment_score_half_steps', 'assessment_score', 'mod(points * 2, 1) = 0'),
]


def upgrade():
    for table in CATALOGS:
        op.add_column(table, sa.Column('created_by', sa.String(length=120), nullable=True))
        op.add_column(table, sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column('updated_by', sa.String(length=120), nullable=True))
    op.add_column('training_report', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    for name, table, condition in CHECKS:
        op.create_check_constraint(name, table, condition)


def downgrade():
    for name, table, _ in reversed(CHECKS):
        op.drop_constraint(name, table, type_='check')
    op.drop_column('training_report', 'updated_at')
    for table in reversed(CATALOGS):
        op.drop_column(table, 'updated_by')
        op.drop_column(table, 'updated_at')
        op.drop_column(table, 'created_by')

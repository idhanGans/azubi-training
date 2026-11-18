"""Fertigkeit je Bewertungskategorie (fuer den Fortschritt)

- assessment_category.skill: READING|LISTENING|WRITING|SPEAKING|GRAMMAR|VOCABULARY
  oder NULL. Aendert keine Ergebnisse — nur, zu welcher Fertigkeit eine
  Kategorie im Fortschritt zaehlt.
- Vorbelegung: Kategorien, die genau wie eine Fertigkeit heissen (Lesen, Hören,
  Schreiben, Sprechen, Grammatik, Wortschatz). Alles andere bleibt NULL und wird
  in der Vorlage zugeordnet.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-24 14:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

NAMES = {'lesen': 'READING', 'hören': 'LISTENING', 'schreiben': 'WRITING', 'sprechen': 'SPEAKING',
         'grammatik': 'GRAMMAR', 'wortschatz': 'VOCABULARY'}


def upgrade():
    op.add_column('assessment_category', sa.Column('skill', sa.String(length=20), nullable=True))
    op.create_check_constraint(
        'ck_assessment_category_skill', 'assessment_category',
        "skill IS NULL OR skill IN ('READING', 'LISTENING', 'WRITING', 'SPEAKING', 'GRAMMAR', 'VOCABULARY')")
    conn = op.get_bind()
    for name, code in NAMES.items():
        conn.execute(sa.text('UPDATE assessment_category SET skill = :c WHERE lower(trim(name)) = :n'),
                     {'c': code, 'n': name})


def downgrade():
    op.drop_constraint('ck_assessment_category_skill', 'assessment_category', type_='check')
    op.drop_column('assessment_category', 'skill')

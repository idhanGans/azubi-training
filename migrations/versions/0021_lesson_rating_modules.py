"""Modul-Bewertung: mehrere Module je Termin, leere Felder, mehrere Staerke/Ziel-Codes

Die Dozentinnen behandeln oft 2–3 Module in einem Termin (Google-Formular „Lernfortschritt Sprachkurs"):
- `lesson_rating.module_id` + `unit`: je Termin, Modul, Einheit und Teilnehmer eine Zeile (bisher je Termin +
  Teilnehmer). Bestand: Modul des Termins, Einheit = wievielter nicht abgesagter Termin dieses Moduls im Kurs
  (dieselbe Zaehlung wie bisher `lesson_ratings.unit_numbers`).
- Sterne, Puenktlichkeit, Mitarbeit, Staerke und Ziel duerfen leer sein (gewollte Luecken, werden ignoriert).
- Staerke/Ziel: ein oder mehrere Codes als „V,R".

Downgrade entfernt, was das alte Schema nicht fassen kann (weitere Module je Termin, Bewertungen mit Luecken)
und kuerzt Staerke/Ziel auf den ersten Code — auf prod nur mit Sicherung davor.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-19 12:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None

CODES_RE = "'^[VRWFPL](,[VRWFPL])*$'"
CODES = "('V', 'R', 'W', 'F', 'P', 'L')"
NULLABLE = ('v', 'r', 'w', 'f', 'p', 'pu', 'mi')


def upgrade():
    op.add_column('lesson_rating', sa.Column('module_id', sa.Integer(), nullable=True))
    op.add_column('lesson_rating', sa.Column('unit', sa.SmallInteger(), nullable=True))
    op.execute('UPDATE lesson_rating lr SET module_id = s.module_id FROM course_session s WHERE s.id = lr.session_id')
    op.execute("""
        WITH u AS (SELECT id, row_number() OVER (PARTITION BY course_id, module_id ORDER BY starts_at, id) AS n
                   FROM course_session WHERE status <> 'CANCELLED' AND module_id IS NOT NULL)
        UPDATE lesson_rating lr SET unit = coalesce((SELECT n FROM u WHERE u.id = lr.session_id), 1)""")
    missing = op.get_bind().execute(sa.text('SELECT count(*) FROM lesson_rating WHERE module_id IS NULL')).scalar()
    if missing:
        raise RuntimeError(f'{missing} Modul-Bewertung(en) an Terminen ohne Modul — bitte zuerst das Modul am Termin '
                           'eintragen, dann erneut migrieren.')
    op.alter_column('lesson_rating', 'module_id', nullable=False)
    op.alter_column('lesson_rating', 'unit', nullable=False)
    op.create_foreign_key('fk_lesson_rating_module', 'lesson_rating', 'course_module', ['module_id'], ['id'])
    op.create_index('ix_lesson_rating_module_id', 'lesson_rating', ['module_id'])
    op.create_check_constraint('ck_lesson_rating_unit', 'lesson_rating', 'unit BETWEEN 1 AND 99')
    op.drop_constraint('uq_lesson_rating_session_trainee', 'lesson_rating', type_='unique')
    op.create_unique_constraint('uq_lesson_rating_sheet_trainee', 'lesson_rating',
                                ['session_id', 'module_id', 'unit', 'trainee_id'])
    for name in NULLABLE:
        op.alter_column('lesson_rating', name, nullable=True)
    for name in ('strength', 'target'):
        op.drop_constraint(f'ck_lesson_rating_{name}', 'lesson_rating', type_='check')
        op.alter_column('lesson_rating', name, type_=sa.String(length=11), nullable=True)
        op.create_check_constraint(f'ck_lesson_rating_{name}', 'lesson_rating', f'{name} ~ {CODES_RE}')


def downgrade():
    op.execute("""DELETE FROM lesson_rating WHERE id NOT IN
                  (SELECT min(id) FROM lesson_rating GROUP BY session_id, trainee_id)""")
    op.execute('DELETE FROM lesson_rating WHERE ' + ' OR '.join(f'{n} IS NULL' for n in (*NULLABLE, 'strength', 'target')))
    for name in ('strength', 'target'):
        op.drop_constraint(f'ck_lesson_rating_{name}', 'lesson_rating', type_='check')
        op.execute(f'UPDATE lesson_rating SET {name} = left({name}, 1)')
        op.alter_column('lesson_rating', name, type_=sa.String(length=1), nullable=False)
        op.create_check_constraint(f'ck_lesson_rating_{name}', 'lesson_rating', f'{name} IN {CODES}')
    for name in NULLABLE:
        op.alter_column('lesson_rating', name, nullable=False)
    op.drop_constraint('uq_lesson_rating_sheet_trainee', 'lesson_rating', type_='unique')
    op.create_unique_constraint('uq_lesson_rating_session_trainee', 'lesson_rating', ['session_id', 'trainee_id'])
    op.drop_constraint('ck_lesson_rating_unit', 'lesson_rating', type_='check')
    op.drop_index('ix_lesson_rating_module_id', table_name='lesson_rating')
    op.drop_constraint('fk_lesson_rating_module', 'lesson_rating', type_='foreignkey')
    op.drop_column('lesson_rating', 'unit')
    op.drop_column('lesson_rating', 'module_id')

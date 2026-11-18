"""Kandidatenverwaltung: Status + Sprachniveaus (konfigurierbar), Kandidaten-Felder

- candidate_status, language_level: Stammdaten-Listen mit Startwerten
- trainee: Kandidaten-Nr. (Sequenz, K-00001; Bestand nach id nummeriert),
  Telefon, Geburtsdatum, Ausbildungsberuf, Status, aktuelles/Ziel-Niveau,
  Start/voraussichtliches Ende, updated_at, created_by, updated_by.
  Bestehende Kandidaten bekommen KEINEN Status/Niveau gesetzt — das ist eine
  fachliche Entscheidung, die das Team im Profil trifft.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

STATUSES = [
    ('PROSPECT', 'Interessent'),
    ('ENTRANCE_EXAM', 'Aufnahmeprüfung'),
    ('LANGUAGE_COURSE', 'Im Sprachkurs'),
    ('EXAM_PREPARATION', 'Prüfungsvorbereitung'),
    ('READY_FOR_TRAINING', 'Bereit für Ausbildung'),
    ('COMPLETED', 'Abgeschlossen'),
    ('PAUSED', 'Pausiert'),
    ('DROPPED_OUT', 'Ausgeschieden'),
]
LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1']


def _catalog(name):
    table = op.create_table(
        name,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name=f'uq_{name}_code'),
    )
    return table


def upgrade():
    statuses = _catalog('candidate_status')
    levels = _catalog('language_level')
    op.bulk_insert(statuses, [{'code': c, 'name': n, 'sort_order': (i + 1) * 10}
                              for i, (c, n) in enumerate(STATUSES)])
    op.bulk_insert(levels, [{'code': c, 'name': c, 'sort_order': (i + 1) * 10}
                            for i, c in enumerate(LEVELS)])

    op.execute('CREATE SEQUENCE candidate_no_seq')
    op.add_column('trainee', sa.Column('candidate_no', sa.String(length=20), nullable=True))
    # Bestand in id-Reihenfolge durchnummerieren (row_number ist deterministisch,
    # nextval() in einem UPDATE waere es nicht), danach die Sequenz dahinter setzen.
    op.execute("UPDATE trainee SET candidate_no = 'K-' || lpad(o.n::text, 5, '0') "
               "FROM (SELECT id, row_number() OVER (ORDER BY id) AS n FROM trainee) o "
               "WHERE trainee.id = o.id")
    op.execute("SELECT setval('candidate_no_seq', COALESCE(max(n), 1), max(n) IS NOT NULL) "
               "FROM (SELECT row_number() OVER () AS n FROM trainee) c")
    op.alter_column('trainee', 'candidate_no', nullable=False,
                    server_default=sa.text("'K-' || lpad(nextval('candidate_no_seq')::text, 5, '0')"))
    op.create_unique_constraint('uq_trainee_candidate_no', 'trainee', ['candidate_no'])

    op.add_column('trainee', sa.Column('phone', sa.String(length=40), nullable=True))
    op.add_column('trainee', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('trainee', sa.Column('target_occupation', sa.String(length=120), nullable=True))
    op.add_column('trainee', sa.Column('status_id', sa.Integer(), nullable=True))
    op.add_column('trainee', sa.Column('current_level_id', sa.Integer(), nullable=True))
    op.add_column('trainee', sa.Column('target_level_id', sa.Integer(), nullable=True))
    op.add_column('trainee', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('trainee', sa.Column('expected_completion_date', sa.Date(), nullable=True))
    op.add_column('trainee', sa.Column('created_by', sa.String(length=120), nullable=True))
    op.add_column('trainee', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trainee', sa.Column('updated_by', sa.String(length=120), nullable=True))
    op.create_foreign_key('fk_trainee_status', 'trainee', 'candidate_status', ['status_id'], ['id'])
    op.create_foreign_key('fk_trainee_current_level', 'trainee', 'language_level', ['current_level_id'], ['id'])
    op.create_foreign_key('fk_trainee_target_level', 'trainee', 'language_level', ['target_level_id'], ['id'])
    op.create_index('ix_trainee_status_id', 'trainee', ['status_id'])
    op.create_index('ix_trainee_current_level_id', 'trainee', ['current_level_id'])
    op.create_check_constraint(
        'ck_trainee_completion_after_start', 'trainee',
        'expected_completion_date IS NULL OR start_date IS NULL OR expected_completion_date >= start_date')


def downgrade():
    op.drop_constraint('ck_trainee_completion_after_start', 'trainee', type_='check')
    op.drop_index('ix_trainee_current_level_id', table_name='trainee')
    op.drop_index('ix_trainee_status_id', table_name='trainee')
    for fk in ('fk_trainee_target_level', 'fk_trainee_current_level', 'fk_trainee_status'):
        op.drop_constraint(fk, 'trainee', type_='foreignkey')
    for col in ('updated_by', 'updated_at', 'created_by', 'expected_completion_date', 'start_date',
                'target_level_id', 'current_level_id', 'status_id', 'target_occupation',
                'date_of_birth', 'phone'):
        op.drop_column('trainee', col)
    op.drop_constraint('uq_trainee_candidate_no', 'trainee', type_='unique')
    op.drop_column('trainee', 'candidate_no')
    op.execute('DROP SEQUENCE candidate_no_seq')
    op.drop_table('language_level')
    op.drop_table('candidate_status')

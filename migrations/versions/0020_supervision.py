"""SPV/Leiter-Zuordnung + Bewertungen fuer die Gesamtbewertung: `department`, `department_leader`,
`trainee.department_id`/`supervisor`, `staff_rating`

- Abteilung (Team) je Kandidat; Leiter (Logins) sehen und bewerten ALLE Kandidaten ihrer Abteilung, der SPV
  (`trainee.supervisor`) nur seine. Bestand: die Abteilung ergibt sich deterministisch aus dem Teil von
  `trainee.abteilung` vor „ – " („Erkelenz – PV-Assistent" -> „Erkelenz", „Netzantrag" -> „Netzantrag").
- `staff_rating` ersetzt `leiter_rating` (Sprache/Technik/Einstellung): Praktische Leistung, Zuverlaessigkeit,
  Motivation & Verhalten je 1..10, Art SPV/LEITER/INTERN. `leiter_rating` bleibt unveraendert stehen
  (prod und release: 0 Zeilen beim Umstieg).

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-09 10:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None

#: Teil der Platzierung vor dem Gedankenstrich (auch „ - ") = Abteilung
_DEPARTMENT_OF = r"btrim(regexp_replace(abteilung, '\s+[–-]\s+.*$', ''))"


def upgrade():
    op.create_table(
        'department',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.UniqueConstraint('name', name='department_name_key'),
        sa.CheckConstraint("btrim(name) <> ''", name='ck_department_name'),
    )
    op.create_table(
        'department_leader',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('department_id', sa.Integer(),
                  sa.ForeignKey('department.id', name='fk_department_leader_department'), nullable=False),
        sa.Column('username', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.UniqueConstraint('department_id', 'username', name='uq_department_leader'),
        sa.CheckConstraint('username = lower(username)', name='ck_department_leader_lower'),
    )
    op.create_index('ix_department_leader_department_id', 'department_leader', ['department_id'])
    op.create_index('ix_department_leader_username', 'department_leader', ['username'])

    op.add_column('trainee', sa.Column('department_id', sa.Integer(), nullable=True))
    op.add_column('trainee', sa.Column('supervisor', sa.String(length=120), nullable=True))
    op.create_foreign_key('fk_trainee_department', 'trainee', 'department', ['department_id'], ['id'])
    op.create_index('ix_trainee_department_id', 'trainee', ['department_id'])
    op.create_index('ix_trainee_supervisor', 'trainee', ['supervisor'])
    op.create_check_constraint('ck_trainee_supervisor_lower', 'trainee', 'supervisor = lower(supervisor)')

    op.execute(f"""INSERT INTO department (name)
                   SELECT DISTINCT {_DEPARTMENT_OF} FROM trainee
                    WHERE abteilung IS NOT NULL AND {_DEPARTMENT_OF} <> '' ORDER BY 1""")
    op.execute(f"""UPDATE trainee t SET department_id = d.id FROM department d
                    WHERE t.abteilung IS NOT NULL AND d.name = {_DEPARTMENT_OF.replace('abteilung', 't.abteilung')}""")

    op.create_table(
        'staff_rating',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trainee_id', sa.Integer(), sa.ForeignKey('trainee.id', name='fk_staff_rating_trainee'),
                  nullable=False),
        sa.Column('rater', sa.String(length=120), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        *(sa.Column(name, sa.SmallInteger(), nullable=False)
          for name in ('r_practical', 'r_reliability', 'r_motivation')),
        sa.Column('note', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.CheckConstraint("kind IN ('SPV', 'LEITER', 'INTERN')", name='ck_staff_rating_kind'),
        *(sa.CheckConstraint(f'{name} BETWEEN 1 AND 10', name=f'ck_staff_rating_{name}')
          for name in ('r_practical', 'r_reliability', 'r_motivation')),
    )
    op.create_index('ix_staff_rating_trainee_id', 'staff_rating', ['trainee_id'])
    op.create_index('ix_staff_rating_rater', 'staff_rating', ['rater'])


def downgrade():
    op.drop_table('staff_rating')
    op.drop_constraint('ck_trainee_supervisor_lower', 'trainee', type_='check')
    op.drop_index('ix_trainee_supervisor', table_name='trainee')
    op.drop_index('ix_trainee_department_id', table_name='trainee')
    op.drop_constraint('fk_trainee_department', 'trainee', type_='foreignkey')
    op.drop_column('trainee', 'supervisor')
    op.drop_column('trainee', 'department_id')
    op.drop_table('department_leader')
    op.drop_table('department')

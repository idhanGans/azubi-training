"""RBAC + Archivieren + zeitzonenbewusste Zeitstempel

- neue Tabelle user_role (Team-Rollen je MSH-Login)
- trainee.archived_at/archived_by (Archivieren ersetzt das harte Loeschen)
- activity_log.action 40 -> 80 Zeichen
- created_at aller Tabellen: timestamp -> timestamptz. Die Bestandswerte wurden
  mit datetime.utcnow() geschrieben, sind also UTC — `AT TIME ZONE 'UTC'`
  deutet sie genau so, kein Wert verschiebt sich.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

_TABLES = ('trainee', 'training_report', 'leiter_rating', 'activity_log')
_ROLES = ('SUPER_ADMIN', 'HR', 'ACADEMIC_MANAGER', 'INSTRUCTOR', 'MANAGEMENT')


def upgrade():
    op.create_table(
        'user_role',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=120), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username', 'role', name='uq_user_role_username_role'),
        sa.CheckConstraint("role IN ({})".format(', '.join(f"'{r}'" for r in _ROLES)),
                           name='ck_user_role_role'),
        sa.CheckConstraint('username = lower(username)', name='ck_user_role_username_lower'),
    )
    op.create_index('ix_user_role_username', 'user_role', ['username'])

    op.add_column('trainee', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trainee', sa.Column('archived_by', sa.String(length=120), nullable=True))

    op.alter_column('activity_log', 'action', type_=sa.String(length=80),
                    existing_type=sa.String(length=40), existing_nullable=False)

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN created_at TYPE timestamptz "
                   f"USING created_at AT TIME ZONE 'UTC'")


def downgrade():
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN created_at TYPE timestamp "
                   f"USING created_at AT TIME ZONE 'UTC'")
    # Scheitert bewusst, falls inzwischen laengere Aktionen protokolliert sind
    # (z.B. 'trainee.restore' passt, aber kuenftige koennten laenger sein) —
    # lieber ein roter Downgrade als ein still abgeschnittener Audit-Trail.
    op.alter_column('activity_log', 'action', type_=sa.String(length=40),
                    existing_type=sa.String(length=80), existing_nullable=False)
    op.drop_column('trainee', 'archived_by')
    op.drop_column('trainee', 'archived_at')
    op.drop_index('ix_user_role_username', table_name='user_role')
    op.drop_table('user_role')

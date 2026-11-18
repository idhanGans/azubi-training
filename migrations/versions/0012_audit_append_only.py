"""Verlauf (activity_log) unveraenderlich + schneller filterbar

- Trigger: UPDATE und DELETE auf activity_log werden von der Datenbank selbst
  abgelehnt — auch wenn Code (oder ein Skript mit dem App-Login) es versucht.
  Neue Eintraege (INSERT) bleiben der einzige Schreibweg.
- Indizes fuer die Filter im Verlauf: (entity_type, entity_id) und actor.

Bestehende Eintraege bleiben unveraendert.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-25 12:00:00
"""
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION activity_log_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'activity_log ist unveraenderlich (%), Eintraege koennen nur angehaengt werden', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute('CREATE TRIGGER activity_log_append_only BEFORE UPDATE OR DELETE ON activity_log '
               'FOR EACH ROW EXECUTE FUNCTION activity_log_append_only()')
    op.create_index('ix_activity_log_entity', 'activity_log', ['entity_type', 'entity_id'])
    op.create_index('ix_activity_log_actor', 'activity_log', ['actor'])


def downgrade():
    op.drop_index('ix_activity_log_actor', table_name='activity_log')
    op.drop_index('ix_activity_log_entity', table_name='activity_log')
    op.execute('DROP TRIGGER activity_log_append_only ON activity_log')
    op.execute('DROP FUNCTION activity_log_append_only()')

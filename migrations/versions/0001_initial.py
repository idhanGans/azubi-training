"""initial schema — trainee, training_report, leiter_rating, activity_log

Revision ID: 0001
Revises:
Create Date: 2026-09-15 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'trainee',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('nickname', sa.String(length=120), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('fach', sa.String(length=20), nullable=True),
        sa.Column('msh_user', sa.String(length=120), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('msh_user'),
    )
    op.create_index('ix_trainee_msh_user', 'trainee', ['msh_user'])

    op.create_table(
        'training_report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trainee_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=12), nullable=True),
        sa.Column('hours', sa.Float(), nullable=True),
        sa.Column('lang', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('tech', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('learned', sa.Text(), nullable=True),
        sa.Column('station', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trainee_id'], ['trainee.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_training_report_trainee_id', 'training_report', ['trainee_id'])

    op.create_table(
        'leiter_rating',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trainee_id', sa.Integer(), nullable=False),
        sa.Column('rater', sa.String(length=120), nullable=True),
        sa.Column('period', sa.String(length=12), nullable=True),
        sa.Column('r_language', sa.Integer(), nullable=True),
        sa.Column('r_technical', sa.Integer(), nullable=True),
        sa.Column('r_attitude', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trainee_id'], ['trainee.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leiter_rating_trainee_id', 'leiter_rating', ['trainee_id'])

    op.create_table(
        'activity_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor', sa.String(length=120), nullable=True),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('entity_type', sa.String(length=30), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(length=200), nullable=True),
        sa.Column('summary', sa.String(length=400), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_activity_log_action', 'activity_log', ['action'])
    op.create_index('ix_activity_log_entity_type', 'activity_log', ['entity_type'])
    op.create_index('ix_activity_log_created_at', 'activity_log', ['created_at'])


def downgrade():
    op.drop_table('activity_log')
    op.drop_index('ix_leiter_rating_trainee_id', table_name='leiter_rating')
    op.drop_table('leiter_rating')
    op.drop_index('ix_training_report_trainee_id', table_name='training_report')
    op.drop_table('training_report')
    op.drop_index('ix_trainee_msh_user', table_name='trainee')
    op.drop_table('trainee')

"""Staff ratings per program month: `staff_rating.month`

The Azubi program runs 3 months; SPV, leader and internal team rate once per month. All existing ratings
belong to month 1 (decision of the operator, 09.11.2026). One rating per (candidate, rater, month).

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-09 10:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('staff_rating', sa.Column('month', sa.SmallInteger(), nullable=False, server_default='1'))
    op.alter_column('staff_rating', 'month', server_default=None)
    op.create_check_constraint('ck_staff_rating_month', 'staff_rating', 'month BETWEEN 1 AND 3')
    op.create_unique_constraint('uq_staff_rating_month', 'staff_rating', ['trainee_id', 'rater', 'month'])


def downgrade():
    op.drop_constraint('uq_staff_rating_month', 'staff_rating', type_='unique')
    op.drop_constraint('ck_staff_rating_month', 'staff_rating', type_='check')
    op.drop_column('staff_rating', 'month')

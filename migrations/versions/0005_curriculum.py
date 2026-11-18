"""Curriculum: Programme, Curricula (je Programm + Niveau), Module, Lernmaterial

- program; trainee.program_id (Kandidat -> Programm, optional)
- curriculum: UNIQUE (program_id, level_id) — genau ein Lehrplan je Niveau
- course_module: Reihenfolge, Dauer, Lernziele (JSON-Liste), Status
- material: Link ODER Datei (CHECK), Datei nur ueber storage_key (zufaellig)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-23 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

_STATUS_CHECK = "status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')"
_TYPES = "('PDF', 'VIDEO', 'DOCUMENT', 'LINK', 'IMAGE', 'EXERCISE', 'HOMEWORK')"


def _audit_columns():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
    ]


def upgrade():
    op.create_table(
        'program',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint('name', name='uq_program_name'),
    )
    op.add_column('trainee', sa.Column('program_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_trainee_program', 'trainee', 'program', ['program_id'], ['id'])
    op.create_index('ix_trainee_program_id', 'trainee', ['program_id'])

    op.create_table(
        'curriculum',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('program_id', sa.Integer(), sa.ForeignKey('program.id', name='fk_curriculum_program'), nullable=False),
        sa.Column('level_id', sa.Integer(), sa.ForeignKey('language_level.id', name='fk_curriculum_level'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='DRAFT'),
        *_audit_columns(),
        sa.UniqueConstraint('program_id', 'level_id', name='uq_curriculum_program_level'),
        sa.CheckConstraint(_STATUS_CHECK, name='ck_curriculum_status'),
    )
    op.create_index('ix_curriculum_program_id', 'curriculum', ['program_id'])

    op.create_table(
        'course_module',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('curriculum_id', sa.Integer(), sa.ForeignKey('curriculum.id', name='fk_module_curriculum'), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_hours', sa.Numeric(6, 1), nullable=True),
        sa.Column('learning_objectives', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='DRAFT'),
        *_audit_columns(),
        sa.CheckConstraint(_STATUS_CHECK, name='ck_course_module_status'),
        sa.CheckConstraint('duration_hours IS NULL OR duration_hours > 0', name='ck_course_module_duration'),
    )
    op.create_index('ix_course_module_curriculum_id', 'course_module', ['curriculum_id'])

    op.create_table(
        'material',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('module_id', sa.Integer(), sa.ForeignKey('course_module.id', name='fk_material_module'), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('storage_key', sa.String(length=64), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('content_type', sa.String(length=120), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        *_audit_columns(),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_by', sa.String(length=120), nullable=True),
        sa.UniqueConstraint('storage_key', name='uq_material_storage_key'),
        sa.CheckConstraint(f'type IN {_TYPES}', name='ck_material_type'),
        sa.CheckConstraint('url IS NULL OR storage_key IS NULL', name='ck_material_link_or_file'),
    )
    op.create_index('ix_material_module_id', 'material', ['module_id'])


def downgrade():
    op.drop_table('material')
    op.drop_table('course_module')
    op.drop_table('curriculum')
    op.drop_index('ix_trainee_program_id', table_name='trainee')
    op.drop_constraint('fk_trainee_program', 'trainee', type_='foreignkey')
    op.drop_column('trainee', 'program_id')
    op.drop_table('program')

"""Bewertungs-Engine: Vorlagen mit gewichteten Kategorien, Bewertungen, Punkte

- assessment_template: Name (unter den nicht archivierten eindeutig), Niveau
  (optional), Bestehensgrenze in Prozent
- assessment_category / assessment_criterion: Kategorien mit Hoechstpunkten,
  Gewicht, Mindestpunkten; optionale Unterkategorien
- assessment: Kandidat + Vorlage + Pruefer + Datum, Status DRAFT|FINAL,
  gespeichertes Ergebnis, Feedback fuer den Kandidaten, interne Notiz getrennt
- assessment_score: Punkte je Kategorie ODER Unterkategorie

Startwert: EINE Beispiel-Vorlage „B1 Monatsbewertung" (frei aenderbar,
solange sie nicht benutzt wurde). Nur neue Tabellen — bestehende Daten bleiben
unberuehrt.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

#: Beispiel-Vorlage (Startwert). Kategorien mit Unterkategorien: max = Summe.
SEED_TEMPLATE = {
    'name': 'B1 Monatsbewertung', 'level_code': 'B1', 'passing_percent': 60,
    'description': 'Monatliche Bewertung aller sechs Fertigkeiten auf B1-Niveau. '
                   'Bestanden ab 60 % gesamt und mindestens 60 % in jeder Fertigkeit.',
    'categories': [
        ('Lesen', 20, 1, 12, []),
        ('Hören', 20, 1, 12, []),
        ('Schreiben', 25, 1, 15, ['Grammatik', 'Satzbau', 'Wortschatz', 'Inhalt', 'Rechtschreibung']),
        ('Sprechen', 25, 1, 15, ['Aussprache', 'Flüssigkeit', 'Wortschatz', 'Grammatik', 'Interaktion']),
        ('Grammatik', 20, 1, 12, []),
        ('Wortschatz', 20, 1, 12, []),
    ],
}


def upgrade():
    op.create_table(
        'assessment_template',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('level_id', sa.Integer(), sa.ForeignKey('language_level.id', name='fk_assessment_template_level'),
                  nullable=True),
        sa.Column('passing_percent', sa.Numeric(5, 1), nullable=False, server_default='60'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_by', sa.String(length=120), nullable=True),
        sa.CheckConstraint('passing_percent BETWEEN 0 AND 100', name='ck_assessment_template_passing'),
    )
    op.create_index('uq_assessment_template_name_active', 'assessment_template', [sa.text('lower(name)')],
                    unique=True, postgresql_where=sa.text('archived_at IS NULL'))

    op.create_table(
        'assessment_category',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('assessment_template.id', ondelete='CASCADE',
                                                             name='fk_assessment_category_template'), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('max_score', sa.Numeric(6, 1), nullable=False),
        sa.Column('weight', sa.Numeric(6, 2), nullable=False),
        sa.Column('passing_score', sa.Numeric(6, 1), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint('max_score > 0', name='ck_assessment_category_max'),
        sa.CheckConstraint('weight > 0', name='ck_assessment_category_weight'),
        sa.CheckConstraint('passing_score IS NULL OR passing_score BETWEEN 0 AND max_score',
                           name='ck_assessment_category_passing'),
    )
    op.create_index('ix_assessment_category_template_id', 'assessment_category', ['template_id'])

    op.create_table(
        'assessment_criterion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('assessment_category.id', ondelete='CASCADE',
                                                             name='fk_assessment_criterion_category'), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('max_score', sa.Numeric(6, 1), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint('max_score > 0', name='ck_assessment_criterion_max'),
    )
    op.create_index('ix_assessment_criterion_category_id', 'assessment_criterion', ['category_id'])

    op.create_table(
        'assessment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('trainee_id', sa.Integer(), sa.ForeignKey('trainee.id', name='fk_assessment_trainee'), nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('assessment_template.id', name='fk_assessment_template'),
                  nullable=False),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('instructor.id', name='fk_assessment_instructor'),
                  nullable=False),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('course.id', name='fk_assessment_course'), nullable=True),
        sa.Column('assessed_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='DRAFT'),
        sa.Column('overall_percent', sa.Numeric(5, 1), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column('strengths', sa.Text(), nullable=True),
        sa.Column('improvements', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('general_feedback', sa.Text(), nullable=True),
        sa.Column('internal_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=120), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finalized_by', sa.String(length=120), nullable=True),
        sa.CheckConstraint("status IN ('DRAFT', 'FINAL')", name='ck_assessment_status'),
        sa.CheckConstraint("status = 'DRAFT' OR (overall_percent IS NOT NULL AND passed IS NOT NULL)",
                           name='ck_assessment_final_result'),
        sa.CheckConstraint('overall_percent IS NULL OR overall_percent BETWEEN 0 AND 100',
                           name='ck_assessment_overall'),
    )
    for column in ('trainee_id', 'template_id', 'instructor_id', 'course_id'):
        op.create_index(f'ix_assessment_{column}', 'assessment', [column])

    op.create_table(
        'assessment_score',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('assessment.id', ondelete='CASCADE',
                                                               name='fk_assessment_score_assessment'), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('assessment_category.id',
                                                             name='fk_assessment_score_category'), nullable=True),
        sa.Column('criterion_id', sa.Integer(), sa.ForeignKey('assessment_criterion.id',
                                                              name='fk_assessment_score_criterion'), nullable=True),
        sa.Column('points', sa.Numeric(6, 1), nullable=False),
        sa.UniqueConstraint('assessment_id', 'category_id', name='uq_assessment_score_category'),
        sa.UniqueConstraint('assessment_id', 'criterion_id', name='uq_assessment_score_criterion'),
        sa.CheckConstraint('(category_id IS NULL) <> (criterion_id IS NULL)', name='ck_assessment_score_target'),
        sa.CheckConstraint('points >= 0', name='ck_assessment_score_points'),
    )
    op.create_index('ix_assessment_score_assessment_id', 'assessment_score', ['assessment_id'])

    _seed(op.get_bind())


def _seed(conn):
    t = SEED_TEMPLATE
    template_id = conn.execute(sa.text(
        "INSERT INTO assessment_template (name, description, level_id, passing_percent, created_by) "
        "VALUES (:n, :d, (SELECT id FROM language_level WHERE code = :lvl), :p, 'migration') RETURNING id"),
        {'n': t['name'], 'd': t['description'], 'lvl': t['level_code'], 'p': t['passing_percent']}).scalar()
    for position, (name, max_score, weight, passing, criteria) in enumerate(t['categories']):
        category_id = conn.execute(sa.text(
            'INSERT INTO assessment_category (template_id, name, max_score, weight, passing_score, position) '
            'VALUES (:t, :n, :m, :w, :p, :o) RETURNING id'),
            {'t': template_id, 'n': name, 'm': max_score, 'w': weight, 'p': passing, 'o': position}).scalar()
        for sub_position, sub in enumerate(criteria):
            conn.execute(sa.text('INSERT INTO assessment_criterion (category_id, name, max_score, position) '
                                 'VALUES (:c, :n, :m, :o)'),
                         {'c': category_id, 'n': sub, 'm': max_score / len(criteria), 'o': sub_position})


def downgrade():
    for table in ('assessment_score', 'assessment', 'assessment_criterion', 'assessment_category',
                  'assessment_template'):
        op.drop_table(table)

"""Bewertungsvorlagen: Liste, Anlegen/Bearbeiten, Kopieren, Archivieren, Vorschau-Berechnung.

Lesen: `assessment.view`; Verwalten: `assessment.configure` (Studienleitung, Admin).
Doku: `assessment_docs.py`.
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import auth
from app.extensions import db
from app.models.assessment_template import DEFAULT_PASSING_PERCENT, AssessmentTemplate
from app.models.common import utcnow
from app.services import assessment_templates as svc, assessments, audit, scoring, validation as v

bp = Blueprint('assessment_templates', __name__, url_prefix='/api/assessment-templates')


def _get(tid):
    template = db.session.get(AssessmentTemplate, tid)
    if template is None:
        raise v.NotFound('Vorlage nicht gefunden.')
    return template


def _body(template, used=None):
    used = svc.usage_counts([template.id]).get(template.id, 0) if used is None else used
    return {**template.to_dict(), 'usage_count': used, 'locked': used > 0}


@bp.route('', methods=['GET'])
@auth.require_permission('assessment.view')
def list_templates():
    q = AssessmentTemplate.query.filter(AssessmentTemplate.archived_at.isnot(None)
                                        if request.args.get('archived') == '1'
                                        else AssessmentTemplate.archived_at.is_(None))
    rows = q.order_by(func.lower(AssessmentTemplate.name)).all()
    counts = svc.usage_counts([t.id for t in rows])
    return jsonify({'templates': [_body(t, counts.get(t.id, 0)) for t in rows],
                    'default_passing_percent': DEFAULT_PASSING_PERCENT})


@bp.route('/<int:tid>', methods=['GET'])
@auth.require_permission('assessment.view')
def get_template(tid):
    return jsonify(_body(_get(tid)))


@bp.route('', methods=['POST'])
@auth.require_permission('assessment.configure')
def create_template():
    data = request.get_json(silent=True) or {}
    template = AssessmentTemplate(**svc.read_header(data), created_by=auth.actor())
    svc.set_structure(template, *svc.read_structure(data))
    db.session.add(template)
    db.session.flush()
    audit.log(auth.actor(), 'assessment_template.create', entity_type='assessment_template', entity_id=template.id,
              entity_name=template.name, summary=f'Bewertungsvorlage angelegt: {template.name}',
              detail={'structure': svc.structure_of(template)})
    db.session.commit()
    return jsonify(_body(template, 0)), 201


@bp.route('/<int:tid>', methods=['PATCH'])
@auth.require_permission('assessment.configure')
def update_template(tid):
    template = _get(tid)
    data = request.get_json(silent=True) or {}
    before = {**{k: getattr(template, k) for k in ('name', 'description')},
              'level': template.level.name if template.level else None}
    before_structure = svc.structure_of(template)
    for key, value in svc.read_header(data, template).items():
        setattr(template, key, value)
    if 'categories' in data or 'passing_percent' in data:
        if svc.is_used(template):
            raise v.Conflict(svc.LOCKED, 'categories')
        svc.set_structure(template, *svc.read_structure({**before_structure, **data}))
    skill_changes = svc.read_skills(template, data['skills']) if 'skills' in data else {}
    db.session.flush()
    db.session.refresh(template)
    after = {**{k: getattr(template, k) for k in ('name', 'description')},
             'level': template.level.name if template.level else None}
    changes = audit.diff(before, after)
    after_structure = svc.structure_of(template)
    if skill_changes:
        changes['fertigkeiten'] = skill_changes
    elif after_structure != before_structure:
        changes['struktur'] = [before_structure, after_structure]
    if changes:
        template.updated_by = auth.actor()
        audit.log(auth.actor(), 'assessment_template.update', entity_type='assessment_template',
                  entity_id=template.id, entity_name=template.name,
                  summary=f'Bewertungsvorlage bearbeitet: {template.name}', detail={'changes': changes})
    db.session.commit()
    return jsonify(_body(template))


@bp.route('/<int:tid>/copy', methods=['POST'])
@auth.require_permission('assessment.configure')
def copy_template(tid):
    source = _get(tid)
    data = request.get_json(silent=True) or {}
    name = v.text(data, 'name', 'Name', 160) or svc.copy_name(source.name)
    copy = AssessmentTemplate(**svc.read_header({'name': name, 'description': source.description,
                                                 'level_id': source.level_id}), created_by=auth.actor())
    svc.set_structure(copy, *svc.read_structure(svc.structure_of(source)))
    db.session.add(copy)
    db.session.flush()
    audit.log(auth.actor(), 'assessment_template.create', entity_type='assessment_template', entity_id=copy.id,
              entity_name=copy.name, summary=f'Bewertungsvorlage kopiert: {source.name} → {copy.name}',
              detail={'copied_from': source.id})
    db.session.commit()
    return jsonify(_body(copy, 0)), 201


@bp.route('/<int:tid>/archive', methods=['POST'])
@auth.require_permission('assessment.configure')
def archive_template(tid):
    template = _get(tid)
    if not template.is_archived:
        template.archived_at, template.archived_by = utcnow(), auth.actor()
        audit.log(auth.actor(), 'assessment_template.archive', entity_type='assessment_template',
                  entity_id=template.id, entity_name=template.name,
                  summary=f'Bewertungsvorlage archiviert: {template.name}')
        db.session.commit()
    return jsonify(_body(template))


@bp.route('/<int:tid>/restore', methods=['POST'])
@auth.require_permission('assessment.configure')
def restore_template(tid):
    template = _get(tid)
    if template.is_archived:
        svc.read_header({'name': template.name}, template)      # Name darf nicht vergeben sein
        template.archived_at = template.archived_by = None
        audit.log(auth.actor(), 'assessment_template.restore', entity_type='assessment_template',
                  entity_id=template.id, entity_name=template.name,
                  summary=f'Bewertungsvorlage wiederhergestellt: {template.name}')
        db.session.commit()
    return jsonify(_body(template))


@bp.route('/<int:tid>/evaluate', methods=['POST'])
@auth.require_permission('assessment.view')
def evaluate(tid):
    """Vorschau: Ergebnis fuer eingegebene Punkte — schreibt nichts (eine Rechenstelle fuer Browser + Server)."""
    template = _get(tid)
    points = {k: p for k, p in assessments.read_scores(template, (request.get_json(silent=True) or {})
                                                        .get('scores')).items() if p is not None}
    return jsonify(scoring.evaluate(template, points))

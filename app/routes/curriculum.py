"""Programme und Curricula (Programm -> Sprachniveau -> Curriculum -> Module)."""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.course_module import CourseModule
from app.models.curriculum import Curriculum
from app.models.language_level import LanguageLevel
from app.models.program import Program
from app.services import audit, curriculum as svc, validation as v

bp = Blueprint('curriculum', __name__, url_prefix='/api')


def _get(model, oid, what):
    row = db.session.get(model, oid)
    if row is None:
        raise v.NotFound(f'{what} nicht gefunden.')
    return row


def _body():
    return request.get_json(silent=True) or {}


@bp.route('/programs', methods=['GET'])
@auth.require_permission('curriculum.view')
def list_programs():
    programs = Program.query.order_by(Program.name).all()
    curricula = (Curriculum.query.join(LanguageLevel, LanguageLevel.id == Curriculum.level_id)
                 .order_by(LanguageLevel.sort_order).all())
    summary = svc.curriculum_summary([c.id for c in curricula])
    by_program = {}
    for c in curricula:
        by_program.setdefault(c.program_id, []).append({**c.to_dict(), **summary.get(c.id, {'module_count': 0,
                                                                                           'hours_total': 0.0})})
    return jsonify({'programs': [{**p.to_dict(), 'curricula': by_program.get(p.id, [])} for p in programs]})


@bp.route('/programs', methods=['POST'])
@auth.require_permission('curriculum.create')
def create_program():
    program = Program(**svc.read_program(_body()), created_by=auth.actor())
    db.session.add(program)
    db.session.flush()
    audit.log(auth.actor(), 'program.create', entity_type='program', entity_id=program.id,
              entity_name=program.name, summary=f'Programm angelegt: {program.name}')
    db.session.commit()
    return jsonify(program.to_dict()), 201


@bp.route('/programs/<int:pid>', methods=['PATCH'])
@auth.require_permission('curriculum.edit')
def update_program(pid):
    program = _get(Program, pid, 'Programm')
    before = program.to_dict()
    for key, value in svc.read_program(_body(), program).items():
        setattr(program, key, value)
    changes = {k: val for k, val in audit.diff(before, program.to_dict()).items() if k not in ('updated_at',)}
    if changes:
        program.updated_by = auth.actor()
        audit.log(auth.actor(), 'program.update', entity_type='program', entity_id=program.id,
                  entity_name=program.name, summary=f'Programm bearbeitet: {program.name}',
                  detail={'changes': changes})
    db.session.commit()
    return jsonify(program.to_dict())


@bp.route('/programs/<int:pid>/curricula', methods=['POST'])
@auth.require_permission('curriculum.create')
def create_curriculum(pid):
    program = _get(Program, pid, 'Programm')
    curriculum = svc.new_curriculum(program, _body(), auth.actor())
    db.session.add(curriculum)
    db.session.flush()
    db.session.refresh(curriculum)
    name = f'{program.name} {curriculum.level.name}'
    audit.log(auth.actor(), 'curriculum.create', entity_type='curriculum', entity_id=curriculum.id,
              entity_name=name, summary=f'Curriculum angelegt: {name}')
    db.session.commit()
    return jsonify(curriculum.to_dict()), 201


@bp.route('/curricula/<int:cid>', methods=['GET'])
@auth.require_permission('curriculum.view')
def get_curriculum(cid):
    curriculum = _get(Curriculum, cid, 'Curriculum')
    modules = CourseModule.query.filter_by(curriculum_id=cid).order_by(CourseModule.position).all()
    counts = svc.material_counts([m.id for m in modules])
    summary = svc.curriculum_summary([cid]).get(cid, {'module_count': 0, 'hours_total': 0.0})
    return jsonify({'curriculum': {**curriculum.to_dict(), **summary},
                    'modules': [{**m.to_dict(), 'material_count': counts.get(m.id, 0)} for m in modules]})


@bp.route('/curricula/<int:cid>', methods=['PATCH'])
@auth.require_permission('curriculum.edit')
def update_curriculum(cid):
    curriculum = _get(Curriculum, cid, 'Curriculum')
    before = curriculum.to_dict()
    for key, value in svc.read_curriculum(_body()).items():
        setattr(curriculum, key, value)
    changes = {k: val for k, val in audit.diff(before, curriculum.to_dict()).items() if k not in ('updated_at',)}
    if changes:
        curriculum.updated_by = auth.actor()
        name = f'{curriculum.program.name} {curriculum.level.name}'
        audit.log(auth.actor(), 'curriculum.update', entity_type='curriculum', entity_id=cid,
                  entity_name=name, summary=f'Curriculum bearbeitet: {name}', detail={'changes': changes})
    db.session.commit()
    return jsonify(curriculum.to_dict())


@bp.route('/curricula/<int:cid>/modules', methods=['POST'])
@auth.require_permission('curriculum.create')
def create_module(cid):
    curriculum = _get(Curriculum, cid, 'Curriculum')
    module = CourseModule(**svc.read_module(_body()), curriculum_id=curriculum.id, created_by=auth.actor(),
                          position=svc.next_position(CourseModule, curriculum_id=curriculum.id))
    db.session.add(module)
    db.session.flush()
    audit.log(auth.actor(), 'module.create', entity_type='module', entity_id=module.id,
              entity_name=module.name, summary=f'Modul angelegt: {module.name}')
    db.session.commit()
    return jsonify(module.to_dict()), 201


@bp.route('/curricula/<int:cid>/module-order', methods=['PUT'])
@auth.require_permission('curriculum.edit')
def reorder_modules(cid):
    _get(Curriculum, cid, 'Curriculum')
    modules = CourseModule.query.filter_by(curriculum_id=cid).all()
    svc.reorder(modules, _body().get('module_ids'), 'module_ids')
    audit.log(auth.actor(), 'module.reorder', entity_type='curriculum', entity_id=cid,
              summary='Modul-Reihenfolge geändert', detail={'module_ids': _body().get('module_ids')})
    db.session.commit()
    return jsonify({'module_ids': [m.id for m in sorted(modules, key=lambda m: m.position)]})

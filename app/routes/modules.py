"""Module (Lernziele, Dauer, Status) und ihr Lernmaterial."""
from flask import Blueprint, current_app, jsonify, request

from app import auth
from app.extensions import db
from app.models.course_module import CourseModule
from app.models.curriculum import Curriculum
from app.models.material import Material
from app.services import audit, curriculum as svc, file_types, validation as v

bp = Blueprint('modules', __name__, url_prefix='/api/modules')


def get_module(mid):
    module = db.session.get(CourseModule, mid)
    if module is None:
        raise v.NotFound('Modul nicht gefunden.')
    return module


@bp.route('', methods=['GET'])
@auth.require_permission('curriculum.view')
def list_for_level():
    """Nicht archivierte Module aller Curricula eines Niveaus (Auswahl im Kurs-Formular)."""
    level_id = v.integer(request.args, 'level_id', 'Sprachniveau', 1, 2**31 - 1)
    if level_id is None:
        raise v.ValidationError('Bitte ein Sprachniveau angeben.', 'level_id')
    modules = (CourseModule.query.join(Curriculum, Curriculum.id == CourseModule.curriculum_id)
               .filter(Curriculum.level_id == level_id, CourseModule.status != 'ARCHIVED')
               .order_by(Curriculum.program_id, CourseModule.position).all())
    return jsonify({'modules': [m.to_dict() for m in modules]})


@bp.route('/<int:mid>', methods=['GET'])
@auth.require_permission('curriculum.view')
def get(mid):
    module = get_module(mid)
    q = Material.query.filter_by(module_id=mid)
    if request.args.get('archived') != '1':
        q = q.filter(Material.archived_at.is_(None))
    return jsonify({'module': module.to_dict(), 'curriculum': module.curriculum.to_dict(),
                    'materials': [m.to_dict() for m in q.order_by(Material.position)],
                    'upload_rules': {'extensions': file_types.ALLOWED_BY_TYPE,
                                     'max_mb': current_app.config['MAX_UPLOAD_BYTES'] // (1024 * 1024)}})


@bp.route('/<int:mid>', methods=['PATCH'])
@auth.require_permission('curriculum.edit')
def update(mid):
    module = get_module(mid)
    before = module.to_dict()
    for key, value in svc.read_module(request.get_json(silent=True) or {}, module).items():
        setattr(module, key, value)
    db.session.flush()
    changes = {k: val for k, val in audit.diff(before, module.to_dict()).items() if k not in ('updated_at',)}
    if changes:
        module.updated_by = auth.actor()
        audit.log(auth.actor(), 'module.update', entity_type='module', entity_id=module.id,
                  entity_name=module.name, summary=f'Modul bearbeitet: {module.name}', detail={'changes': changes})
    db.session.commit()
    return jsonify(module.to_dict())


@bp.route('/<int:mid>/material-order', methods=['PUT'])
@auth.require_permission('curriculum.edit')
def reorder_materials(mid):
    get_module(mid)
    materials = Material.query.filter_by(module_id=mid).filter(Material.archived_at.is_(None)).all()
    ids = (request.get_json(silent=True) or {}).get('material_ids')
    svc.reorder(materials, ids, 'material_ids')
    audit.log(auth.actor(), 'material.reorder', entity_type='module', entity_id=mid,
              summary='Material-Reihenfolge geändert', detail={'material_ids': ids})
    db.session.commit()
    return jsonify({'material_ids': [m.id for m in sorted(materials, key=lambda m: m.position)]})

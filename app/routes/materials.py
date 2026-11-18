"""Lernmaterial: anlegen (Link oder Datei), bearbeiten, Datei ersetzen,
archivieren und — nur mit Rechte-Pruefung — herunterladen."""
from contextlib import contextmanager

from flask import Blueprint, current_app, jsonify, request, send_file

from app import auth
from app.extensions import db, file_store
from app.models.common import utcnow
from app.models.material import Material
from app.routes.modules import get_module
from app.services import audit, curriculum as svc, file_types, materials as mat, validation as v

bp = Blueprint('materials', __name__, url_prefix='/api')


def _get(mid):
    material = db.session.get(Material, mid)
    if material is None:
        raise v.NotFound('Material nicht gefunden.')
    return material


def _form():
    """JSON (Link-Material) oder multipart (mit Datei) — Felder als dict."""
    return request.get_json(silent=True) if request.is_json else request.form.to_dict()


def _store(upload, kind):
    return mat.store_upload(upload, kind, file_store, current_app.config['MAX_UPLOAD_BYTES'])


@contextmanager
def _discard_file_on_error(storage_key):
    """Die Datei liegt schon im Store: scheitert danach irgendetwas an der DB,
    wird sie wieder entfernt — keine verwaisten Dateien."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        if storage_key:
            file_store.delete(storage_key)
        raise


@bp.route('/modules/<int:mid>/materials', methods=['POST'])
@auth.require_permission('curriculum.create')
def create(mid):
    module = get_module(mid)
    data = _form() or {}
    values = mat.read_fields(data)
    upload = request.files.get('file')
    has_file = bool(upload and upload.filename)
    mat.check_complete(values['type'], values.get('url'), has_file, values.get('description'))
    if has_file:
        values.update(_store(upload, values['type']))
    with _discard_file_on_error(values.get('storage_key')):
        material = Material(**values, module_id=module.id, created_by=auth.actor(),
                            position=svc.next_position(Material, module_id=module.id))
        db.session.add(material)
        db.session.flush()
        audit.log(auth.actor(), 'material.create', entity_type='material', entity_id=material.id,
                  entity_name=material.title, summary=f'Material angelegt: {material.title} ({module.name})',
                  detail={'file_name': material.file_name, 'sha256': material.sha256, 'url': material.url})
    return jsonify(material.to_dict()), 201


@bp.route('/materials/<int:mid>', methods=['PATCH'])
@auth.require_permission('curriculum.edit')
def update(mid):
    material = _get(mid)
    values = mat.read_fields(request.get_json(silent=True) or {}, material)
    mat.check_complete(material.type, values.get('url', material.url), material.has_file,
                       values.get('description', material.description))
    before = material.to_dict()
    for key, value in values.items():
        setattr(material, key, value)
    changes = {k: val for k, val in audit.diff(before, material.to_dict()).items() if k != 'updated_at'}
    if changes:
        material.updated_by = auth.actor()
        audit.log(auth.actor(), 'material.update', entity_type='material', entity_id=mid,
                  entity_name=material.title, summary=f'Material bearbeitet: {material.title}',
                  detail={'changes': changes})
    db.session.commit()
    return jsonify(material.to_dict())


@bp.route('/materials/<int:mid>/file', methods=['POST'])
@auth.require_permission('curriculum.edit')
def replace_file(mid):
    """Neue Datei hochladen. Die alte bleibt im Store (Historie, im Protokoll per Hash)."""
    material = _get(mid)
    upload = request.files.get('file')
    if not (upload and upload.filename):
        raise v.ValidationError('Bitte eine Datei auswählen.', 'file')
    if material.url:
        raise v.ValidationError('Dieses Material ist ein Link. Bitte zuerst den Link entfernen.', 'file')
    old = {'file_name': material.file_name, 'sha256': material.sha256, 'storage_key': material.storage_key}
    stored = _store(upload, material.type)
    with _discard_file_on_error(stored['storage_key']):
        for key, value in stored.items():
            setattr(material, key, value)
        material.updated_by = auth.actor()
        audit.log(auth.actor(), 'material.file', entity_type='material', entity_id=mid,
                  entity_name=material.title, summary=f'Datei ersetzt: {material.title}',
                  detail={'old': old, 'new': {'file_name': material.file_name, 'sha256': material.sha256}})
    return jsonify(material.to_dict())


@bp.route('/materials/<int:mid>/archive', methods=['POST'])
@auth.require_permission('curriculum.edit')
def archive(mid):
    material = _get(mid)
    if material.archived_at is None:
        material.archived_at, material.archived_by = utcnow(), auth.actor()
        audit.log(auth.actor(), 'material.archive', entity_type='material', entity_id=mid,
                  entity_name=material.title, summary=f'Material archiviert: {material.title}')
        db.session.commit()
    return jsonify(material.to_dict())


@bp.route('/materials/<int:mid>/restore', methods=['POST'])
@auth.require_permission('curriculum.edit')
def restore(mid):
    material = _get(mid)
    if material.archived_at is not None:
        material.archived_at = material.archived_by = None
        material.position = svc.next_position(Material, module_id=material.module_id)
        audit.log(auth.actor(), 'material.restore', entity_type='material', entity_id=mid,
                  entity_name=material.title, summary=f'Material wiederhergestellt: {material.title}')
        db.session.commit()
    return jsonify(material.to_dict())


@bp.route('/materials/<int:mid>/file', methods=['GET'])
@auth.require_permission('curriculum.view')
def download(mid):
    return send_material_file(_get(mid))


def send_material_file(material):
    """Datei ausliefern — auch fuer das Kandidaten-Portal (dort vorher `portal.material_visible`)."""
    if not material.has_file:
        raise v.NotFound('Zu diesem Material gibt es keine Datei.')
    kind = file_types.KINDS[file_types.extension(material.file_name)]
    response = send_file(file_store.open(material.storage_key), mimetype=material.content_type,
                         as_attachment=not kind.inline, download_name=material.file_name,
                         max_age=0, etag=material.sha256)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-cache'
    if not kind.inline:
        response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return response

"""Stammdaten-Listen (Kandidaten-Status, Sprachniveaus): lesen + pflegen.

Nie loeschen — Kandidaten verweisen darauf; stattdessen `active: false`.
"""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.candidate_status import CandidateStatus
from app.models.language_level import LanguageLevel
from app.services import audit, validation as v

bp = Blueprint('catalogs', __name__, url_prefix='/api/catalogs')

KINDS = {'candidate-status': CandidateStatus, 'language-level': LanguageLevel}


def _model(kind):
    if kind not in KINDS:
        raise v.NotFound('Unbekannte Stammdaten-Liste.')
    return KINDS[kind]


def _read(data, partial):
    has = (lambda key: key in data) if partial else (lambda key: True)
    values = {}
    if has('code'):
        code = v.text(data, 'code', 'Kürzel', 40, required=True).upper()
        if not code.replace('_', '').isalnum():
            raise v.ValidationError('„Kürzel“ darf nur Buchstaben, Ziffern und Unterstriche enthalten.', 'code')
        values['code'] = code
    if has('name'):
        values['name'] = v.text(data, 'name', 'Bezeichnung', 120, required=True)
    if has('sort_order'):
        values['sort_order'] = v.integer(data, 'sort_order', 'Reihenfolge', 0, 10000) or 0
    if 'active' in data:
        values['active'] = bool(data.get('active'))
    return values


def _check_code_free(model, code, row_id=None):
    if code is not None and model.query.filter(model.code == code, model.id != row_id).first():
        raise v.Conflict('Dieses Kürzel ist bereits vergeben.', 'code')


@bp.route('/<kind>', methods=['GET'])
@auth.require_permission('candidate.view')
def list_entries(kind):
    model = _model(kind)
    rows = model.query.order_by(model.sort_order, model.name).all()
    return jsonify({'entries': [r.to_dict() for r in rows]})


@bp.route('/<kind>', methods=['POST'])
@auth.require_permission('system.manage')
def create_entry(kind):
    model = _model(kind)
    values = _read(request.get_json(silent=True) or {}, partial=False)
    _check_code_free(model, values['code'])
    row = model(**values)
    db.session.add(row)
    db.session.flush()
    audit.log(auth.actor(), 'catalog.create', entity_type=kind, entity_id=row.id, entity_name=row.name,
              summary=f'Stammdaten-Eintrag angelegt: {row.name}')
    db.session.commit()
    return jsonify(row.to_dict()), 201


@bp.route('/<kind>/<int:eid>', methods=['PATCH'])
@auth.require_permission('system.manage')
def update_entry(kind, eid):
    model = _model(kind)
    row = db.session.get(model, eid)
    if row is None:
        raise v.NotFound('Eintrag nicht gefunden.')
    values = _read(request.get_json(silent=True) or {}, partial=True)
    _check_code_free(model, values.get('code'), row.id)
    before = row.to_dict()
    for key, value in values.items():
        setattr(row, key, value)
    changes = audit.diff(before, row.to_dict())
    if changes:
        audit.log(auth.actor(), 'catalog.update', entity_type=kind, entity_id=row.id, entity_name=row.name,
                  summary=f'Stammdaten-Eintrag bearbeitet: {row.name}', detail={'changes': changes})
    db.session.commit()
    return jsonify(row.to_dict())


_E = {'id': 3, 'code': 'LANGUAGE_COURSE', 'name': 'Im Sprachkurs', 'sort_order': 30, 'active': True}

DOCS = [
    {'path': '/api/catalogs/<kind>', 'method': 'GET',
     'description': 'Stammdaten-Liste lesen; kind = candidate-status | language-level — candidate.view',
     'response_example': {'entries': [_E]}},
    {'path': '/api/catalogs/<kind>', 'method': 'POST',
     'description': 'Stammdaten-Eintrag anlegen (409 Kürzel vergeben) — system.manage',
     'request_example': {'code': 'LANGUAGE_COURSE', 'name': 'Im Sprachkurs', 'sort_order': 30},
     'response_example': _E},
    {'path': '/api/catalogs/<kind>/<id>', 'method': 'PATCH',
     'description': 'Stammdaten-Eintrag ändern/deaktivieren (kein Löschen) — system.manage',
     'request_example': {'name': 'Im Deutschkurs', 'active': False}, 'response_example': _E},
]

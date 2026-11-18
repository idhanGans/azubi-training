"""Candidate management: list (search/filter/sort/pages), profile, maintenance."""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.common import utcnow
from app.models.trainee import Trainee
from app.services import attendance, audit, candidate_profile, candidate_search, candidates, scope, validation as v

bp = Blueprint('candidates', __name__, url_prefix='/api/candidates')


def _get(cid):
    trainee = db.session.get(Trainee, cid)
    if trainee is None or not scope.can_see_trainee(auth.current_identity(), cid):
        raise v.NotFound('Kandidat nicht gefunden.')
    return trainee


_REFS = ('program', 'status', 'current_level', 'target_level')
_NOT_AUDITED = ('updated_at', 'updated_by', 'program_id', 'status_id', 'current_level_id', 'target_level_id')


def _audit_view(data):
    """For the activity log: master data with NAMES instead of IDs, without administrative fields."""
    view = {k: val for k, val in data.items() if k not in _NOT_AUDITED}
    for key in _REFS:
        view[key] = data[key]['name'] if data[key] else None
    return view


def _query_from_args(args):
    sort = args.get('sort', 'name')
    descending = sort.startswith('-')
    sort = sort.lstrip('-')
    if sort not in candidate_search.SORT_KEYS:
        raise v.ValidationError('Unbekannte Sortierung.', 'sort')
    return candidate_search.Query(
        text=(args.get('q') or '').strip()[:100] or None,
        status_id=v.integer(args, 'status_id', 'Status', 1, 2**31 - 1),
        level_id=v.integer(args, 'level_id', 'Sprachniveau', 1, 2**31 - 1),
        fach=v.text(args, 'fach', 'Fachrichtung', 20),
        archived=args.get('archived') == '1',
        visible=scope.trainee_ids(auth.current_identity()),
        sort=sort, descending=descending,
        page=v.integer(args, 'page', 'Seite', 1, 100000) or 1,
        per_page=v.integer(args, 'per_page', 'Einträge pro Seite', 1, candidate_search.MAX_PER_PAGE) or 25,
    )


@bp.route('', methods=['GET'])
@auth.require_permission('candidate.view')
def list_candidates():
    result = candidate_search.search(_query_from_args(request.args))
    rates = attendance.stats([c['id'] for c in result['items']],
                             scope.course_condition(auth.current_identity()))
    for item in result['items']:
        item['attendance_rate'] = rates.get(item['id'], {}).get('rate')
    return jsonify(result)


@bp.route('/<int:cid>', methods=['GET'])
@auth.require_permission('candidate.view')
def get_candidate(cid):
    return jsonify(candidate_profile.profile(_get(cid), auth.current_identity()))


@bp.route('', methods=['POST'])
@auth.require_permission('candidate.create')
def create_candidate():
    trainee = candidates.read_new(request.get_json(silent=True) or {}, auth.actor())
    db.session.add(trainee)
    db.session.flush()
    audit.log(auth.actor(), 'trainee.create', entity_type='trainee', entity_id=trainee.id,
              entity_name=trainee.name, summary=f'Kandidat angelegt: {trainee.name} ({trainee.candidate_no})')
    db.session.commit()
    return jsonify(trainee.to_dict()), 201


@bp.route('/<int:cid>', methods=['PATCH'])
@auth.require_permission('candidate.edit')
def update_candidate(cid):
    trainee = _get(cid)
    before = _audit_view(trainee.to_dict())
    if candidates.apply_changes(trainee, request.get_json(silent=True) or {}, auth.actor()):
        db.session.flush()
        db.session.refresh(trainee)
        changes = audit.diff(before, _audit_view(trainee.to_dict()))
        audit.log(auth.actor(), 'trainee.update', entity_type='trainee', entity_id=trainee.id,
                  entity_name=trainee.name, summary=f'Kandidat bearbeitet: {trainee.name}',
                  detail={'changes': changes})
    db.session.commit()
    return jsonify(trainee.to_dict())


@bp.route('/<int:cid>/archive', methods=['POST'])
@auth.require_permission('candidate.edit')
def archive_candidate(cid):
    trainee = _get(cid)
    if not trainee.is_archived:
        trainee.archived_at, trainee.archived_by = utcnow(), auth.actor()
        audit.log(auth.actor(), 'trainee.archive', entity_type='trainee', entity_id=trainee.id,
                  entity_name=trainee.name, summary=f'Kandidat archiviert: {trainee.name}')
        db.session.commit()
    return jsonify(trainee.to_dict())


@bp.route('/<int:cid>/restore', methods=['POST'])
@auth.require_permission('candidate.edit')
def restore_candidate(cid):
    trainee = _get(cid)
    if trainee.is_archived:
        trainee.archived_at = trainee.archived_by = None
        audit.log(auth.actor(), 'trainee.restore', entity_type='trainee', entity_id=trainee.id,
                  entity_name=trainee.name, summary=f'Kandidat wiederhergestellt: {trainee.name}')
        db.session.commit()
    return jsonify(trainee.to_dict())

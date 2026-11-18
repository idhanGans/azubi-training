"""Assessments (Bewertungen): list, create (draft), save points/feedback, finalize,
correct, discard draft; candidates see their finalized ones.

Scope (Reichweite) via `scope` (instructors: only candidates of their courses), changes only
with `assessments.can_edit`. Docs: `assessment_docs.py`.
"""
from flask import Blueprint, jsonify, request

from app import auth
from app.extensions import db
from app.models.assessment import STATUSES, Assessment
from app.models.common import utcnow
from app.services import assessments as svc, audit, notifications, scope, scoring, validation as v

bp = Blueprint('assessments', __name__, url_prefix='/api')

#: List paginated — default and upper limit per page.
PER_PAGE, MAX_PER_PAGE = 50, 200


def _get(aid):
    assessment = db.session.get(Assessment, aid)
    if assessment is None or not scope.can_see_trainee(auth.current_identity(), assessment.trainee_id):
        raise v.NotFound('Bewertung nicht gefunden.')
    return assessment


def _editable(aid):
    assessment = _get(aid)
    if not svc.can_edit(auth.current_identity(), assessment):
        raise v.Forbidden('Diese Bewertung kann nur ihr Prüfer oder die Studienleitung ändern.')
    return assessment


def _detail(assessment):
    return {'assessment': assessment.to_dict(), 'template': assessment.template.to_dict(),
            'result': scoring.evaluate(assessment.template, assessment.points()),
            'can_edit': svc.can_edit(auth.current_identity(), assessment), 'history': svc.history(assessment)}


def _label(assessment):
    return f'{assessment.trainee.name} – {assessment.template.name}'


def _pct(value):
    return '–' if value is None else audit.de_number(value) + ' %'


def _log(assessment, action, summary, detail=None, reason=None):
    audit.log(auth.actor(), action, entity_type='trainee', entity_id=assessment.trainee_id,
              entity_name=assessment.trainee.name, summary=summary, reason=reason,
              detail={'assessment_id': assessment.id, **(detail or {})})


def _apply(assessment, data):
    """Take over header fields, texts and points from `data`. Returns {field: [old, new]}."""
    changes = {}
    for key, value in svc.read_changes(data, assessment, auth.current_identity()).items():
        old = getattr(assessment, key)
        if old != value:
            label = svc.FEEDBACK_LABELS.get(key, {'internal_note': 'Interne Notiz', 'assessed_on': 'Datum',
                                                  'instructor_id': 'Prüfer', 'course_id': 'Kurs'}.get(key, key))
            changes[label] = [old.isoformat() if key == 'assessed_on' else old,
                              value.isoformat() if key == 'assessed_on' else value]
            setattr(assessment, key, value)
    changes.update(svc.apply_scores(assessment, svc.read_scores(assessment.template, data.get('scores'))))
    if changes:
        assessment.updated_by = auth.actor()
    return changes


@bp.route('/assessments', methods=['GET'])
@auth.require_permission('assessment.view')
def list_assessments():
    q = scope.restrict(Assessment.query, Assessment.trainee_id, auth.current_identity())
    for name in ('trainee_id', 'template_id', 'instructor_id', 'course_id'):
        value = v.integer(request.args, name, 'Filter', 1, 2**31 - 1)
        if value:
            q = q.filter(getattr(Assessment, name) == value)
    if request.args.get('mine') == '1':
        q = q.filter(Assessment.instructor_id == auth.current_identity().instructor_id)
    status = request.args.get('status')
    if status:
        if status not in STATUSES:
            raise v.ValidationError('Unbekannter Status.', 'status')
        q = q.filter(Assessment.status == status)
    page = v.integer(request.args, 'page', 'Seite', 1, 100000) or 1
    per_page = v.integer(request.args, 'per_page', 'Einträge je Seite', 1, MAX_PER_PAGE) or PER_PAGE
    total = q.order_by(None).count()
    rows = (q.order_by(Assessment.assessed_on.desc(), Assessment.id.desc())
            .limit(per_page).offset((page - 1) * per_page).all())
    return jsonify({'assessments': [a.summary() for a in rows], 'total': total, 'page': page, 'per_page': per_page})


@bp.route('/assessments', methods=['POST'])
@auth.require_permission('assessment.create')
def create_assessment():
    data = request.get_json(silent=True) or {}
    assessment = svc.read_new(data, auth.current_identity(), auth.actor())
    db.session.add(assessment)
    db.session.flush()
    svc.apply_scores(assessment, svc.read_scores(assessment.template, data.get('scores')))
    _log(assessment, 'assessment.create', f'Bewertung angelegt (Entwurf): {_label(assessment)}')
    db.session.commit()
    return jsonify(_detail(assessment)), 201


@bp.route('/assessments/<int:aid>', methods=['GET'])
@auth.require_permission('assessment.view')
def get_assessment(aid):
    return jsonify(_detail(_get(aid)))


@bp.route('/assessments/<int:aid>', methods=['PATCH'])
@auth.require_permission('assessment.edit')
def update_assessment(aid):
    assessment = _editable(aid)
    data = request.get_json(silent=True) or {}
    if assessment.status == 'FINAL':
        svc.allow_result_change()             # correction — logged below with old -> new
    old_result = (assessment.overall_percent, assessment.passed)
    changes = _apply(assessment, data)
    if assessment.status == 'FINAL' and changes:
        # Correction: only with a reason; stays complete, result is recalculated and logged.
        reason = v.text(data, 'reason', 'Grund', 500)
        if not reason:
            raise v.ValidationError('Bitte geben Sie einen Grund für die Korrektur an.', 'reason')
        svc.check_finalizable(assessment, scoring.evaluate(assessment.template, assessment.points()))
        scoring.apply(assessment)
        if old_result[0] != assessment.overall_percent:
            changes['Gesamt'] = [float(old_result[0]), float(assessment.overall_percent)]
        if old_result[1] != assessment.passed:
            changes['Bestanden'] = [old_result[1], assessment.passed]
        notifications.assessment_final(assessment, corrected=True)
        _log(assessment, 'assessment.correct',
             f'Bewertung geändert: {_label(assessment)}: {_pct(old_result[0])} → {_pct(assessment.overall_percent)}',
             {'changes': changes}, reason=reason)
    db.session.commit()
    return jsonify(_detail(assessment))


@bp.route('/assessments/<int:aid>/finalize', methods=['POST'])
@auth.require_permission('assessment.edit')
def finalize_assessment(aid):
    assessment = _editable(aid)
    if assessment.status == 'FINAL':
        raise v.Conflict('Die Bewertung ist bereits abgeschlossen.', 'status')
    svc.allow_result_change()
    _apply(assessment, request.get_json(silent=True) or {})
    svc.check_finalizable(assessment, scoring.evaluate(assessment.template, assessment.points()))
    assessment.status, assessment.finalized_at, assessment.finalized_by = 'FINAL', utcnow(), auth.actor()
    scoring.apply(assessment)
    notifications.assessment_final(assessment)
    verdict = 'bestanden' if assessment.passed else 'nicht bestanden'
    _log(assessment, 'assessment.finalize',
         f'Bewertung abgeschlossen: {_label(assessment)}: {_pct(assessment.overall_percent)} ({verdict})',
         {'overall_percent': float(assessment.overall_percent), 'passed': assessment.passed})
    db.session.commit()
    return jsonify(_detail(assessment))


@bp.route('/assessments/<int:aid>', methods=['DELETE'])
@auth.require_permission('assessment.edit')
def delete_draft(aid):
    assessment = _editable(aid)
    if assessment.status != 'DRAFT':
        raise v.Conflict('Abgeschlossene Bewertungen können nicht gelöscht werden.', 'status')
    _log(assessment, 'assessment.delete', f'Bewertungs-Entwurf verworfen: {_label(assessment)}')
    notifications.resolve(key=f'draft:{assessment.id}')
    db.session.delete(assessment)
    db.session.commit()
    return jsonify({'deleted': aid})


@bp.route('/my-assessments', methods=['GET'])
@auth.candidate_only
def my_assessments():
    """Candidate: only FINALIZED own assessments — without internal note (`public_dict`)."""
    rows = (Assessment.query.filter_by(trainee_id=auth.current_identity().trainee_id, status='FINAL')
            .order_by(Assessment.assessed_on, Assessment.id).all())
    return jsonify({'assessments': [
        {**a.public_dict(), 'categories': scoring.evaluate(a.template, a.points())['categories']} for a in rows]})

"""Programme, Curricula, Module: Eingaben pruefen, Reihenfolge pflegen."""
from sqlalchemy import func

from app.extensions import db
from app.models.course_module import CourseModule
from app.models.curriculum import STATUSES, Curriculum
from app.models.language_level import LanguageLevel
from app.models.material import Material
from app.models.program import Program
from app.services import validation as v

MAX_OBJECTIVES = 30


def _status(data):
    status = data.get('status')
    if status not in STATUSES:
        raise v.ValidationError('Bitte einen gültigen Status auswählen.', 'status')
    return status


def read_program(data, program=None):
    values = {}
    if program is None or 'name' in data:
        values['name'] = v.text(data, 'name', 'Name', 120, required=True)
        other = Program.query.filter(func.lower(Program.name) == values['name'].lower(),
                                     Program.id != getattr(program, 'id', None)).first()
        if other:
            raise v.Conflict('Ein Programm mit diesem Namen gibt es bereits.', 'name')
    if program is None or 'description' in data:
        values['description'] = v.text(data, 'description', 'Beschreibung', 4000)
    if 'active' in data:
        values['active'] = bool(data.get('active'))
    return values


def new_curriculum(program, data, actor):
    level = v.reference(data, 'level_id', 'Sprachniveau', LanguageLevel)
    if level is None:
        raise v.ValidationError('Bitte ein Sprachniveau auswählen.', 'level_id')
    if Curriculum.query.filter_by(program_id=program.id, level_id=level.id).first():
        raise v.Conflict(f'Für {level.name} gibt es in diesem Programm bereits ein Curriculum.', 'level_id')
    return Curriculum(program_id=program.id, level_id=level.id, created_by=actor,
                      description=v.text(data, 'description', 'Beschreibung', 4000))


def read_curriculum(data):
    values = {}
    if 'description' in data:
        values['description'] = v.text(data, 'description', 'Beschreibung', 4000)
    if 'status' in data:
        values['status'] = _status(data)
    return values


def _objectives(data):
    raw = data.get('learning_objectives')
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise v.ValidationError('Lernziele müssen eine Liste sein.', 'learning_objectives')
    items = [str(item).strip() for item in raw if str(item).strip()]
    if len(items) > MAX_OBJECTIVES:
        raise v.ValidationError(f'Höchstens {MAX_OBJECTIVES} Lernziele je Modul.', 'learning_objectives')
    if any(len(item) > 300 for item in items):
        raise v.ValidationError('Ein Lernziel darf höchstens 300 Zeichen lang sein.', 'learning_objectives')
    return items


def read_module(data, module=None):
    has = (lambda key: key in data) if module else (lambda key: True)
    values = {}
    if has('name'):
        values['name'] = v.text(data, 'name', 'Name', 160, required=True)
    if has('description'):
        values['description'] = v.text(data, 'description', 'Beschreibung', 4000)
    if has('duration_hours'):
        values['duration_hours'] = v.number(data, 'duration_hours', 'Dauer (Stunden)', 0.5, 1000)
    if has('learning_objectives'):
        values['learning_objectives'] = _objectives(data)
    if 'status' in data:
        values['status'] = _status(data)
    return values


def next_position(model, **parent):
    current = db.session.query(func.max(model.position)).filter_by(**parent).scalar()
    return (current or 0) + 1


def reorder(rows, ordered_ids, field):
    """Neue Reihenfolge setzen; die IDs muessen GENAU die vorhandenen sein."""
    by_id = {row.id: row for row in rows}
    if not isinstance(ordered_ids, list) or sorted(ordered_ids) != sorted(by_id):
        raise v.ValidationError('Die Reihenfolge muss alle Einträge genau einmal enthalten.', field)
    for position, row_id in enumerate(ordered_ids, start=1):
        by_id[row_id].position = position


def curriculum_summary(curriculum_ids):
    """Je Curriculum: Anzahl Module + Summe Stunden (eine Query)."""
    if not curriculum_ids:
        return {}
    rows = (db.session.query(CourseModule.curriculum_id, func.count(CourseModule.id),
                             func.sum(CourseModule.duration_hours))
            .filter(CourseModule.curriculum_id.in_(curriculum_ids), CourseModule.status != 'ARCHIVED')
            .group_by(CourseModule.curriculum_id))
    return {cid: {'module_count': n, 'hours_total': float(h or 0)} for cid, n, h in rows}


def material_counts(module_ids):
    if not module_ids:
        return {}
    rows = (db.session.query(Material.module_id, func.count(Material.id))
            .filter(Material.module_id.in_(module_ids), Material.archived_at.is_(None))
            .group_by(Material.module_id))
    return dict(rows.all())

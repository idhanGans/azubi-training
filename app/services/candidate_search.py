"""Kandidatenliste: Suche, Filter, Sortierung, Seiten — alles in der Datenbank."""
from dataclasses import dataclass

from sqlalchemy import func, or_

from app.extensions import db
from app.models.candidate_status import CandidateStatus
from app.models.common import iso
from app.models.language_level import LanguageLevel
from app.models.staff_rating import StaffRating
from app.models.trainee import Trainee
from app.models.training_report import TrainingReport
from app.services.courses import courses_of_trainees

MAX_PER_PAGE = 100


@dataclass(frozen=True)
class Query:
    text: str | None = None
    status_id: int | None = None
    level_id: int | None = None
    fach: str | None = None
    archived: bool = False
    visible: object = None      # Subquery sichtbarer IDs (scope.trainee_ids) — None = alle
    sort: str = 'name'
    descending: bool = False
    page: int = 1
    per_page: int = 25


def _escape_like(term):
    return term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def search(q):
    last_rating = (db.session.query(StaffRating.trainee_id, func.max(StaffRating.created_at).label('at'))
                   .group_by(StaffRating.trainee_id).subquery())
    last_report = (db.session.query(TrainingReport.trainee_id, func.max(TrainingReport.created_at).label('at'))
                   .group_by(TrainingReport.trainee_id).subquery())
    level = db.aliased(LanguageLevel)
    base = (db.session.query(Trainee, last_rating.c.at, last_report.c.at)
            .outerjoin(last_rating, last_rating.c.trainee_id == Trainee.id)
            .outerjoin(last_report, last_report.c.trainee_id == Trainee.id)
            .outerjoin(CandidateStatus, CandidateStatus.id == Trainee.status_id)
            .outerjoin(level, level.id == Trainee.current_level_id))
    base = base.filter(Trainee.archived_at.isnot(None) if q.archived else Trainee.archived_at.is_(None))
    if q.visible is not None:
        base = base.filter(Trainee.id.in_(q.visible))
    if q.text:
        like = f'%{_escape_like(q.text)}%'
        base = base.filter(or_(*(col.ilike(like, escape='\\') for col in (
            Trainee.name, Trainee.nickname, Trainee.candidate_no, Trainee.email, Trainee.msh_user))))
    if q.status_id:
        base = base.filter(Trainee.status_id == q.status_id)
    if q.level_id:
        base = base.filter(Trainee.current_level_id == q.level_id)
    if q.fach:
        base = base.filter(Trainee.fach == q.fach)

    sort_columns = {
        'name': func.lower(Trainee.name), 'candidate_no': Trainee.candidate_no,
        'status': CandidateStatus.sort_order, 'level': level.sort_order,
        'last_rating': last_rating.c.at, 'last_report': last_report.c.at,
    }
    column = sort_columns[q.sort]
    order = column.desc().nulls_last() if q.descending else column.asc().nulls_last()
    total = base.order_by(None).count()
    rows = (base.order_by(order, Trainee.id).limit(q.per_page)
            .offset((q.page - 1) * q.per_page).all())
    courses = courses_of_trainees([t.id for t, _, _ in rows])
    items = [{**t.to_dict(), 'last_rating_at': iso(rated), 'last_report_at': iso(reported),
              'courses': courses.get(t.id, [])}
             for t, rated, reported in rows]
    return {'items': items, 'total': total, 'page': q.page, 'per_page': q.per_page}


SORT_KEYS = ('name', 'candidate_no', 'status', 'level', 'last_rating', 'last_report')

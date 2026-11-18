"""In-App-Benachrichtigungen: anlegen (ohne Doppelte), erledigen, lesen.

Zwei Wege:
- Ereignisse (im selben Commit wie die Aenderung): Termin abgesagt/verschoben,
  in Kurs aufgenommen, Bewertung veroeffentlicht/korrigiert.
- Faellige Erinnerungen entstehen beim Abruf (`generate_due`, laeuft vor jeder
  Liste/Zaehlung): Termin morgen, Bewertungs-Entwurf aelter als 3 Tage,
  fehlende Anwesenheit. Es gibt keinen Scheduler — eine In-App-Nachricht sieht
  man ohnehin erst beim Oeffnen der App. `dedupe_key` (UNIQUE je Empfaenger)
  sorgt dafuer, dass jede Erinnerung nur einmal entsteht.
Empfaenger ist der Login (`trainee.msh_user` / `instructor.msh_user`); ohne Login keine Nachricht.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.extensions import db
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_participant import CourseParticipant
from app.models.course_session import CourseSession
from app.models.notification import Notification
from app.models.trainee import Trainee
from app.services import attendance
from app.services.local_time import day_range_utc, today

DRAFT_REMINDER = timedelta(days=3)
ATTENDANCE_GRACE = timedelta(hours=1)
LIST_LIMIT = 100


def notify(recipients, kind, params, link, key):
    """Je Empfaenger eine Nachricht — gibt es sie (gleicher Schluessel) schon, passiert nichts."""
    rows = [{'recipient': r, 'type': kind, 'params': params, 'link': link, 'dedupe_key': key}
            for r in sorted({r for r in recipients if r})]
    if rows:
        db.session.execute(insert(Notification).values(rows)
                           .on_conflict_do_nothing(constraint='uq_notification_recipient_key'))


def resolve(key=None, prefix=None):
    """Erledigte Hinweise (z.B. Entwurf abgeschlossen) fuer alle Empfaenger als gelesen markieren."""
    q = Notification.query.filter(Notification.read_at.is_(None))
    q = q.filter(Notification.dedupe_key == key) if key else q.filter(Notification.dedupe_key.like(f'{prefix}%'))
    q.update({Notification.read_at: func.now()}, synchronize_session=False)


def _session_params(session):
    data = session.public_dict()
    return {'course': data['course']['name'], 'date': data['date'], 'start': data['start'], 'end': data['end'],
            'room': data['room']}


def _candidate_logins(course_id):
    return [login for (login,) in db.session.query(Trainee.msh_user)
            .join(CourseParticipant, CourseParticipant.trainee_id == Trainee.id)
            .filter(CourseParticipant.course_id == course_id, Trainee.archived_at.is_(None),
                    Trainee.msh_user.isnot(None))]


def _instructor_login(session):
    return session.instructor.msh_user if session.instructor and not session.instructor.is_archived else None


# ---------- Ereignisse ----------

def session_changed(session, changes):
    """Nach dem Speichern eines Termins: Absage oder Verschiebung melden (nur kuenftige Termine)."""
    if session.starts_at <= datetime.now(timezone.utc):
        return                                          # vergangene Termine: keine Nachricht mehr
    params = _session_params(session)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    moved = {'date', 'start', 'end'} & set(changes)
    if changes.get('status', [None, None])[1] == 'CANCELLED':
        kind, params = 'SESSION_CANCELLED', {**params, 'reason': session.cancel_reason}
    elif moved and session.status != 'CANCELLED':
        old = {k: changes[k][0] if k in changes else params[k] for k in ('date', 'start', 'end')}
        kind, params = 'SESSION_MOVED', {**params, 'old_date': old['date'], 'old_start': old['start'],
                                         'old_end': old['end']}
    else:
        return
    resolve(prefix=f'reminder:{session.id}:')          # alte Erinnerung passt nicht mehr
    key = f'{kind.lower()}:{session.id}:{stamp}'
    notify(_candidate_logins(session.course_id), kind, params, '/my-schedule', key)
    notify([_instructor_login(session)], kind, params, f'/schedule?view=day&date={params["date"]}', key)


def course_joined(course, trainees):
    notify([t.msh_user for t in trainees if not t.is_archived], 'COURSE_JOINED', {'course': course.name},
           '/my-course', f'course:{course.id}')


def assessment_final(assessment, corrected=False):
    trainee = assessment.trainee
    if trainee.msh_user and not trainee.is_archived:
        kind = 'ASSESSMENT_CORRECTED' if corrected else 'ASSESSMENT_PUBLISHED'
        key = f'assessment:{assessment.id}' + (f':{datetime.now(timezone.utc):%Y%m%d%H%M%S}' if corrected else '')
        notify([trainee.msh_user], kind, {'template': assessment.template.name,
                                          'date': assessment.assessed_on.isoformat()}, '/my-assessments', key)
    resolve(key=f'draft:{assessment.id}')


# ---------- Faellige Erinnerungen ----------

def generate_due(identity):
    """Erinnerungen fuer DIESEN Nutzer anlegen, die jetzt faellig sind (idempotent)."""
    login, now = identity.username, datetime.now(timezone.utc)
    tomorrow = today() + timedelta(days=1)
    start, end = day_range_utc(tomorrow, tomorrow)
    base = (CourseSession.query.join(Course, Course.id == CourseSession.course_id)
            .filter(CourseSession.status != 'CANCELLED', Course.archived_at.is_(None),
                    CourseSession.starts_at >= start, CourseSession.starts_at < end))
    if identity.trainee_id is not None:
        own = db.select(CourseParticipant.course_id).where(CourseParticipant.trainee_id == identity.trainee_id)
        for s in base.filter(CourseSession.course_id.in_(own)):
            notify([login], 'SESSION_REMINDER', _session_params(s), '/my-schedule',
                   f'reminder:{s.id}:{s.starts_at.isoformat()}')
    if identity.instructor_id is not None:
        for s in base.filter(CourseSession.instructor_id == identity.instructor_id):
            params = _session_params(s)
            notify([login], 'SESSION_REMINDER', params, f'/schedule?view=day&date={params["date"]}',
                   f'reminder:{s.id}:{s.starts_at.isoformat()}')
        for a in Assessment.query.filter(Assessment.instructor_id == identity.instructor_id,
                                         Assessment.status == 'DRAFT', Assessment.created_at < now - DRAFT_REMINDER):
            notify([login], 'ASSESSMENT_DRAFT_OPEN', {'candidate': a.trainee.name, 'template': a.template.name,
                                                      'date': a.assessed_on.isoformat()},
                   f'/assessments/{a.id}', f'draft:{a.id}')
        for s in attendance.open_sessions(identity.instructor_id):
            if s.ends_at < now - ATTENDANCE_GRACE:
                notify([login], 'ATTENDANCE_MISSING', _session_params(s), '/teaching', f'attendance:{s.id}')
    db.session.commit()


# ---------- Lesen ----------

def for_user(login, unread_only=False):
    q = Notification.query.filter_by(recipient=login)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    return q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(LIST_LIMIT).all()


def unread_count(login):
    return Notification.query.filter_by(recipient=login).filter(Notification.read_at.is_(None)).count()


def mark_read(login, notification_id=None):
    q = Notification.query.filter(Notification.recipient == login, Notification.read_at.is_(None))
    if notification_id is not None:
        q = q.filter(Notification.id == notification_id)
    return q.update({Notification.read_at: func.now()}, synchronize_session=False)

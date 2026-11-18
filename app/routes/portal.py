"""Kandidaten-Portal: Uebersicht, Profil, Kurs, Module + Material — nur die EIGENEN Daten.

Alle Routen `candidate_only`; die Kandidaten-ID kommt aus dem Token, nie aus dem
Request. Fremdes Material antwortet mit 404. Keine internen Notizen, keine
Team-Logins, keine anderen Kandidaten.
"""
from flask import Blueprint, jsonify

from app import auth
from app.extensions import db
from app.models.assessment import Assessment
from app.models.material import Material
from app.models.trainee import Trainee
from app.routes.materials import send_material_file
from app.services import attendance, portal, progress, validation as v

bp = Blueprint('portal', __name__, url_prefix='/api')


def _me():
    return db.session.get(Trainee, auth.current_identity().trainee_id)


def _course(course, sessions):
    return {'id': course.id, 'name': course.name, 'description': course.description, 'status': course.status,
            'level': course.level.ref(), 'instructor': {'name': course.instructor.name} if course.instructor else None,
            'module': {'id': course.module.id, 'name': course.module.name} if course.module else None,
            'next_sessions': [s.public_dict() for s in sessions if s.course_id == course.id][:5]}


@bp.route('/my-profile', methods=['GET'])
@auth.candidate_only
def my_profile():
    return jsonify({'candidate': _me().public_dict()})


@bp.route('/my-courses', methods=['GET'])
@auth.candidate_only
def my_courses():
    rows = portal.courses(_me().id)
    sessions = portal.next_sessions([c.id for c in rows], 50)
    return jsonify({'courses': [_course(c, sessions) for c in rows]})


@bp.route('/my-modules', methods=['GET'])
@auth.candidate_only
def my_modules():
    return jsonify({'curricula': portal.modules(_me().id)})


@bp.route('/my-materials/<int:mid>/file', methods=['GET'])
@auth.candidate_only
def my_material_file(mid):
    material = db.session.get(Material, mid)
    if material is None or not portal.material_visible(_me().id, material):
        raise v.NotFound('Material nicht gefunden.')
    return send_material_file(material)


@bp.route('/my-overview', methods=['GET'])
@auth.candidate_only
def my_overview():
    """Startseite: heute (Termine + Tages-Report), naechste Termine, Anwesenheit, letzte Bewertung + Feedback,
    Module, Fertigkeiten."""
    me = _me()
    rows = portal.courses(me.id)
    latest = (Assessment.query.filter_by(trainee_id=me.id, status='FINAL')
              .order_by(Assessment.assessed_on.desc(), Assessment.id.desc()).first())
    skills = progress.assessments(me.id)['skills']
    return jsonify({
        'candidate': me.public_dict(),
        'today': portal.today_tasks(me.id, [c.id for c in rows]),
        'next_sessions': [s.public_dict() for s in portal.next_sessions([c.id for c in rows], 3)],
        'attendance': attendance.stats_for(me.id),
        'latest_assessment': latest.public_dict() if latest else None,
        'modules': [{k: m[k] for k in ('curriculum', 'course', 'current', 'completed', 'total', 'percent')}
                    for m in progress.modules(me.id)],
        'skills': [{k: s[k] for k in ('skill', 'current', 'change', 'count')} for s in skills],
    })


_ME = {'id': 5, 'candidate_no': 'K-00005', 'name': 'Agus Prakoso', 'nickname': 'Agus', 'email': 'agus@example.org',
       'phone': None, 'date_of_birth': None, 'fach': 'Elektro', 'abteilung': 'Berlin – Elektro',
       'target_occupation': 'Elektroniker', 'program': {'id': 1, 'name': 'Deutsch für Azubis – Sprechkurs'},
       'status': {'id': 3, 'code': 'LANGUAGE_COURSE', 'name': 'Im Sprachkurs'},
       'current_level': {'id': 3, 'code': 'B1', 'name': 'B1'}, 'target_level': {'id': 4, 'code': 'B2', 'name': 'B2'},
       'start_date': '2026-08-14', 'expected_completion_date': '2027-03-23', 'msh_user': 'agus'}
_SESSION = {'id': 7, 'date': '2026-09-28', 'start': '09:00', 'end': '11:00', 'room': 'R 1.02', 'location': 'Berlin',
            'status': 'SCHEDULED', 'course': {'id': 1, 'name': 'Sprechkurs B1 – Gruppe Nina'}}
_MOD = {'curriculum': {'id': 1, 'program': 'Deutsch für Azubis – Sprechkurs', 'level': {'code': 'B1'}},
        'course': {'id': 1, 'name': 'Sprechkurs B1 – Gruppe Nina', 'status': 'RUNNING'},
        'current': {'id': 7, 'name': 'Modul 7 – Fehler & Probleme'}, 'completed': 6, 'total': 18, 'percent': 33.3}

DOCS = [
    {'path': '/api/my-overview', 'method': 'GET',
     'description': 'Kandidat: Startseite — eigene Stammdaten, heute (eigene Termine heute + ob der Tages-Report '
                    'für heute abgegeben ist), nächste 3 Termine, Anwesenheitsquote, letzte '
                    'abgeschlossene Bewertung (mit Feedback, ohne interne Notiz), Module, Fertigkeiten',
     'response_example': {'candidate': _ME,
                          'today': {'date': '2026-09-28', 'sessions': [_SESSION], 'report_done': False},
                          'next_sessions': [_SESSION],
                          'attendance': {'present': 15, 'late': 2, 'excused': 1, 'absent': 1, 'recorded': 19,
                                         'rate': 0.9444},
                          'latest_assessment': {'id': 9, 'assessed_on': '2026-09-19', 'overall_percent': 79.1,
                                                'passed': True, 'template': {'id': 1, 'name': 'B1 Monatsbewertung'},
                                                'recommendations': 'Konnektoren wiederholen'},
                          'modules': [_MOD], 'skills': [{'skill': 'SPEAKING', 'current': 82.0, 'change': 5.6,
                                                         'count': 4}]}},
    {'path': '/api/my-profile', 'method': 'GET',
     'description': 'Kandidat: eigene Stammdaten (nur lesen; ohne Team-Logins)', 'response_example': {'candidate': _ME}},
    {'path': '/api/my-courses', 'method': 'GET',
     'description': 'Kandidat: eigene Kurse mit Dozent (Name), aktuellem Modul und nächsten Terminen — keine '
                    'Teilnehmerliste',
     'response_example': {'courses': [{'id': 1, 'name': 'Sprechkurs B1 – Gruppe Nina', 'description': None,
                                       'status': 'RUNNING', 'level': {'id': 3, 'code': 'B1', 'name': 'B1'},
                                       'instructor': {'name': 'Nina'},
                                       'module': {'id': 7, 'name': 'Modul 7 – Fehler & Probleme'},
                                       'next_sessions': [_SESSION]}]}},
    {'path': '/api/my-modules', 'method': 'GET',
     'description': 'Kandidat: Module des Curriculums der eigenen Kurse mit Stand (done/current/open), Lernzielen '
                    'und Material (Datei über /api/my-materials/<id>/file)',
     'response_example': {'curricula': [{**_MOD, 'modules': [{
         'id': 1, 'name': 'Modul 1 – Ankommen in Deutschland', 'description': 'Sich vorstellen …',
         'duration_hours': None, 'learning_objectives': ['Sich vorstellen'], 'state': 'done',
         'materials': [{'id': 3, 'type': 'PDF', 'title': 'Fragenkatalog – Modul 1', 'description': None,
                        'url': None, 'has_file': True, 'file_name': 'Fragenkatalog_Modul_01.pdf',
                        'size_bytes': 151226}]}]}]}},
    {'path': '/api/my-materials/<id>/file', 'method': 'GET',
     'description': 'Kandidat: Datei eines Materials aus dem eigenen Curriculum (sonst 404); PDF/Bilder inline',
     'response_example': '(Dateiinhalt, z.B. application/pdf)'},
]

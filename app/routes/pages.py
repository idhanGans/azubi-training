"""HTML pages (Jinja). Each page then loads its data itself via /api.

Access is governed by the same declaration as for the API (`app/auth.py`); the
sidebar shows only pages whose rule the user satisfies.
"""
from flask import Blueprint, redirect, render_template

from app import auth, navigation

bp = Blueprint('pages', __name__)


def _page(template, title, i18n_key, **context):
    return render_template(f'pages/{template}.html', page_title=title, page_i18n=i18n_key, **context)


@bp.route('/')
@auth.authenticated
def home():
    target = navigation.home_url(auth.current_identity())
    if target is None:
        return render_template('pages/no_access.html', page_title='Kein Zugriff',
                               page_i18n='noaccess_title'), 403
    return redirect(target)


@bp.route('/my')
@auth.candidate_only
def my_overview():
    return _page('my_overview', 'Übersicht', 'nav_my_overview')


@bp.route('/my-profile')
@auth.candidate_only
def my_profile():
    return _page('my_profile', 'Mein Profil', 'nav_my_profile')


@bp.route('/my-course')
@auth.candidate_only
def my_course():
    return _page('my_course', 'Mein Kurs', 'nav_my_course')


@bp.route('/my-modules')
@auth.candidate_only
def my_modules():
    return _page('my_modules', 'Meine Module', 'nav_my_modules')


@bp.route('/my-feedback')
@auth.candidate_only
def my_feedback():
    return _page('my_feedback', 'Mein Feedback', 'nav_my_feedback')


@bp.route('/my-notifications')
@auth.candidate_only
def my_notifications():
    return _page('notifications', 'Benachrichtigungen', 'nt_title')


@bp.route('/notifications')
@auth.authenticated
def notifications():
    return _page('notifications', 'Benachrichtigungen', 'nt_title')


@bp.route('/my-reports')
@auth.candidate_only
def my_reports():
    return _page('my_reports', 'Mein Trainings-Report', 'nav_my_reports')


@bp.route('/my-schedule')
@auth.candidate_only
def my_schedule():
    return _page('my_schedule', 'Mein Stundenplan', 'nav_my_schedule')


@bp.route('/my-attendance')
@auth.candidate_only
def my_attendance():
    return _page('my_attendance', 'Meine Anwesenheit', 'nav_my_attendance')


@bp.route('/my-assessments')
@auth.candidate_only
def my_assessments():
    return _page('my_assessments', 'Meine Bewertungen', 'nav_my_assessments')


@bp.route('/my-progress')
@auth.candidate_only
def my_progress():
    return _page('my_progress', 'Mein Fortschritt', 'nav_my_progress')


@bp.route('/assessments')
@auth.require_permission('assessment.view')
def assessments():
    return _page('assessments', 'Bewertungen', 'nav_assessments')


@bp.route('/assessments/<int:aid>')
@auth.require_permission('assessment.view')
def assessment(aid):
    return _page('assessment', 'Bewertung', 'page_assessment', assessment_id=aid, nav_active='pages.assessments',
                 parent_crumb=('pages.assessments', 'nav_assessments', 'Bewertungen'))


@bp.route('/assessment-templates')
@auth.require_permission('assessment.view')
def assessment_templates():
    return _page('assessment_templates', 'Bewertungsvorlagen', 'page_assessment_templates',
                 nav_active='pages.assessments', parent_crumb=('pages.assessments', 'nav_assessments', 'Bewertungen'))


@bp.route('/dashboard')
@auth.require_permission('candidate.view')
def dashboard():
    return _page('dashboard', 'Übersicht', 'nav_dashboard')


@bp.route('/schedule')
@auth.require_permission('schedule.view')
def schedule():
    return _page('schedule', 'Stundenplan', 'nav_schedule')


@bp.route('/teaching')
@auth.instructor_only
def teaching():
    return _page('teaching', 'Mein Unterricht', 'nav_teaching')


@bp.route('/candidates')
@auth.require_permission('candidate.view')
def candidates():
    return _page('candidates', 'Kandidaten', 'nav_candidates')


@bp.route('/candidates/<int:cid>')
@auth.require_permission('candidate.view')
def candidate(cid):
    return _page('candidate', 'Kandidatenprofil', 'page_candidate', candidate_id=cid,
                 nav_active='pages.candidates',
                 parent_crumb=('pages.candidates', 'nav_candidates', 'Kandidaten'))


@bp.route('/courses')
@auth.require_permission('schedule.view')
def courses():
    return _page('courses', 'Kurse', 'nav_courses')


@bp.route('/courses/<int:cid>')
@auth.require_permission('schedule.view')
def course(cid):
    return _page('course', 'Kurs', 'page_course', course_id=cid,
                 nav_active='pages.courses', parent_crumb=('pages.courses', 'nav_courses', 'Kurse'))


@bp.route('/instructors')
@auth.require_permission('instructor.view')
def instructors():
    return _page('instructors', 'Dozenten', 'nav_instructors')


@bp.route('/curriculum')
@auth.require_permission('curriculum.view')
def curriculum():
    return _page('curriculum', 'Curriculum', 'nav_curriculum')


@bp.route('/curriculum/<int:cid>')
@auth.require_permission('curriculum.view')
def curriculum_detail(cid):
    return _page('curriculum_detail', 'Curriculum', 'nav_curriculum', curriculum_id=cid,
                 nav_active='pages.curriculum', parent_crumb=('pages.curriculum', 'nav_curriculum', 'Curriculum'))


@bp.route('/modules/<int:mid>')
@auth.require_permission('curriculum.view')
def module(mid):
    return _page('module', 'Modul', 'page_module', module_id=mid,
                 nav_active='pages.curriculum', parent_crumb=('pages.curriculum', 'nav_curriculum', 'Curriculum'))


@bp.route('/training')
@auth.require_permission('candidate.view')
def training():
    return _page('training', 'Trainings-Monitoring', 'nav_training')


@bp.route('/sessions/<int:sid>/lesson')
@auth.require_permission('assessment.view')
def lesson(sid):
    return _page('lesson', 'Modul-Bewertung', 'page_lesson', session_id=sid, nav_active='pages.lesson_reports',
                 parent_crumb=('pages.lesson_reports', 'nav_lesson_reports', 'Modul-Auswertung'))


@bp.route('/lesson-reports')
@auth.require_permission('assessment.view')
def lesson_reports():
    return _page('lesson_reports', 'Modul-Auswertung', 'nav_lesson_reports')


@bp.route('/ratings')
@auth.require_permission('rating.view')
def ratings():
    return _page('ratings', 'Mitarbeiter-Bewertung', 'nav_ratings')


@bp.route('/reports')
@auth.require_permission('report.view')
def reports():
    return _page('reports', 'Berichte', 'nav_reports')


@bp.route('/reports/candidates/<int:cid>')
@auth.require_permission('report.view')
def candidate_report(cid):
    return _page('candidate_report', 'Kandidatenbericht', 'page_candidate_report', candidate_id=cid,
                 nav_active='pages.reports', parent_crumb=('pages.reports', 'nav_reports', 'Berichte'))


@bp.route('/overall')
@auth.require_permission('rating.view')
def overall():
    return _page('overall', 'Gesamtbewertung', 'nav_overall')


@bp.route('/overall/months')
@auth.require_permission('report.view')
def overall_months():
    return _page('overall_months', 'Monatsvergleich', 'nav_overall_months')


@bp.route('/overall/<int:tid>')
@auth.require_permission('rating.view')
def overall_trainee(tid):
    return _page('overall_trainee', 'Azubi-Bericht', 'page_overall_trainee', trainee_id=tid,
                 nav_active='pages.overall', parent_crumb=('pages.overall', 'nav_overall', 'Gesamtbewertung'))


@bp.route('/users')
@auth.require_permission('user.manage')
def users():
    return _page('users', 'Benutzerverwaltung', 'nav_users')


@bp.route('/settings')
@auth.require_permission('system.manage')
def settings():
    return _page('settings', 'Stammdaten', 'nav_settings')


@bp.route('/activity')
@auth.require_permission('audit.view')
def activity():
    return _page('activity', 'Verlauf', 'nav_activity')


def _html(path, what):
    return {'path': path, 'method': 'GET', 'description': f'{what} (HTML-Seite)',
            'response_example': '<!doctype html> … (text/html, kein JSON)'}


DOCS = [
    _html('/', 'Startseite — leitet auf die erste Seite weiter, die die Rolle sehen darf'),
    _html('/my', 'Kandidat: Übersicht (Startseite des Portals)'),
    _html('/my-profile', 'Kandidat: eigene Stammdaten (nur lesen)'),
    _html('/my-course', 'Kandidat: eigene Kurse mit Dozent, Modul und nächsten Terminen'),
    _html('/my-modules', 'Kandidat: Module mit Lernzielen und Lernmaterial'),
    _html('/my-feedback', 'Kandidat: Feedback aus abgeschlossenen Bewertungen'),
    _html('/my-notifications', 'Kandidat: Benachrichtigungen (Menüpunkt im Portal)'),
    _html('/notifications', 'Eigene Benachrichtigungen (über die Glocke) — angemeldet'),
    _html('/my-reports', 'Kandidat: eigener Trainings-Report'),
    _html('/my-schedule', 'Kandidat: eigener Stundenplan (kommende Termine)'),
    _html('/my-attendance', 'Kandidat: eigene Anwesenheit (Quote + Einträge)'),
    _html('/my-assessments', 'Kandidat: eigene abgeschlossene Bewertungen mit Feedback'),
    _html('/my-progress', 'Kandidat: eigener Fortschritt (Fertigkeiten, Module, Anwesenheit)'),
    _html('/assessments', 'Bewertungen: Liste mit Filtern (assessment.view; Dozenten: Kandidaten ihrer Kurse)'),
    _html('/assessments/<id>', 'Bewertung: Punkte erfassen, Ergebnis, Feedback, interne Notiz (assessment.view)'),
    _html('/assessment-templates', 'Bewertungsvorlagen mit Kategorien und Gewichten (assessment.view)'),
    _html('/dashboard', 'Team: Übersicht mit Kennzahlen und Handlungsbedarf je Rolle (candidate.view)'),
    _html('/schedule', 'Stundenplan: Kalender Tag/Woche/Monat mit Filtern (schedule.view; Dozenten: nur eigene Kurse)'),
    _html('/teaching', 'Dozent: Mein Unterricht — eigene Kurse und Teilnehmer'),
    _html('/courses', 'Kurse mit Niveau, Modul, Dozent (schedule.view; Dozenten: nur eigene)'),
    _html('/courses/<id>', 'Kurs: Teilnehmer, Dozent, Modul (schedule.view)'),
    _html('/instructors', 'Dozentenverwaltung (instructor.view)'),
    _html('/candidates', 'Team: Kandidatenliste mit Suche/Filter/Sortierung (candidate.view)'),
    _html('/candidates/<id>', 'Team: Kandidatenprofil (candidate.view)'),
    _html('/curriculum', 'Programme mit Sprachniveaus und Curricula (curriculum.view)'),
    _html('/curriculum/<id>', 'Curriculum: Module in Reihenfolge (curriculum.view)'),
    _html('/modules/<id>', 'Modul: Lernziele und Lernmaterial (curriculum.view)'),
    _html('/training', 'Team: Trainings-Monitoring (candidate.view)'),
    _html('/sessions/<id>/lesson', 'Modul-Bewertung eines Termins: ganze Gruppe mit Anwesenheit, Sternen, '
          'Lernverhalten, Stärke/Ziel (assessment.view, erfassen assessment.create)'),
    _html('/lesson-reports', 'Modul-Auswertung je Gruppe: Durchschnitte, Trend, schwächster Aspekt, Level (assessment.view)'),
    _html('/ratings', 'Bewertung durch SPV/Leiter/internes Team: zugeordnete Kandidaten bewerten, Durchschnitte, '
          'eigene Bewertungen (rating.view)'),
    _html('/reports', 'Berichte: Anwesenheit, Leistung, Dozenten mit Zeitraum, Filtern und CSV (report.view)'),
    _html('/reports/candidates/<id>', 'Kandidatenbericht, druckbar (report.view)'),
    _html('/overall', 'Gesamtbewertung: Rangliste gesamt/je Abteilung mit Report, Deutsch, SPV, Intern; Excel/PDF '
          '(rating.view; ohne report.view nur zugeordnete Kandidaten)'),
    _html('/overall/months', 'Monatsvergleich: alle Azubis je Programm-Monat, Änderung Monat A -> B, Trend, '
          'Kennzahlen und Diagramm (report.view)'),
    _html('/overall/<id>', 'Azubi-Bericht: Teile der Gesamtbewertung mit Herleitung und Bewertungen; Excel/PDF '
          '(rating.view)'),
    _html('/users', 'Benutzerverwaltung (user.manage)'),
    _html('/settings', 'Stammdaten: Kandidaten-Status, Sprachniveaus (system.manage)'),
    _html('/activity', 'Verlauf/Audit-Trail (audit.view)'),
]

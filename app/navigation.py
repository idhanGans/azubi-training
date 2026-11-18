"""Sidebar (Seitenleiste): which pages exist — visible is whatever the access
rule of the page allows the user. There is NO second permission list for the menu.
"""
from dataclasses import dataclass

from flask import current_app, g, url_for

from app import auth


@dataclass(frozen=True)
class NavItem:
    endpoint: str
    i18n_key: str
    label: str      # German — the translation is done by static/js/i18n.js
    icon: str       # icon name from static/icons.svg (without "i-")


NAV_ITEMS = (
    # Candidate portal (Kandidaten-Portal) (order as specified; "Übersicht" is thus the home page)
    NavItem('pages.my_overview', 'nav_my_overview', 'Übersicht', 'home'),
    NavItem('pages.my_reports', 'nav_my_reports', 'Mein Trainings-Report', 'pen'),    # daily duty: on top
    NavItem('pages.my_profile', 'nav_my_profile', 'Mein Profil', 'idcard'),
    NavItem('pages.my_schedule', 'nav_my_schedule', 'Mein Stundenplan', 'calendar'),
    NavItem('pages.my_course', 'nav_my_course', 'Mein Kurs', 'building'),
    NavItem('pages.my_modules', 'nav_my_modules', 'Meine Module', 'book'),
    NavItem('pages.my_assessments', 'nav_my_assessments', 'Meine Bewertungen', 'award'),
    NavItem('pages.my_progress', 'nav_my_progress', 'Mein Fortschritt', 'trending'),
    NavItem('pages.my_attendance', 'nav_my_attendance', 'Meine Anwesenheit', 'check-circle'),
    NavItem('pages.my_feedback', 'nav_my_feedback', 'Mein Feedback', 'message'),
    NavItem('pages.my_notifications', 'nav_my_notifications', 'Benachrichtigungen', 'bell'),
    NavItem('pages.teaching', 'nav_teaching', 'Mein Unterricht', 'presentation'),
    # Team home page (instructors start at "Mein Unterricht")
    NavItem('pages.dashboard', 'nav_dashboard', 'Übersicht', 'chart'),
    NavItem('pages.candidates', 'nav_candidates', 'Kandidaten', 'users'),
    NavItem('pages.schedule', 'nav_schedule', 'Stundenplan', 'calendar'),
    NavItem('pages.courses', 'nav_courses', 'Kurse', 'layers'),
    NavItem('pages.assessments', 'nav_assessments', 'Bewertungen', 'clipboard'),
    NavItem('pages.lesson_reports', 'nav_lesson_reports', 'Modul-Auswertung', 'star'),
    # every staff login (SPV/leader: assigned candidates); home page for those without a team role
    NavItem('pages.ratings', 'nav_ratings', 'Bewerten', 'pen'),
    NavItem('pages.curriculum', 'nav_curriculum', 'Curriculum', 'book'),
    NavItem('pages.instructors', 'nav_instructors', 'Dozenten', 'briefcase'),
    NavItem('pages.training', 'nav_training', 'Trainings-Monitoring', 'graduation'),
    NavItem('pages.reports', 'nav_reports', 'Berichte', 'file'),
    NavItem('pages.overall', 'nav_overall', 'Gesamtbewertung', 'award'),
    NavItem('pages.overall_months', 'nav_overall_months', 'Monatsvergleich', 'trending'),
    NavItem('pages.users', 'nav_users', 'Benutzerverwaltung', 'shield'),
    NavItem('pages.settings', 'nav_settings', 'Stammdaten', 'sliders'),
    NavItem('pages.activity', 'nav_activity', 'Verlauf', 'history'),
)


def visible_items(identity):
    return [item for item in NAV_ITEMS
            if auth.is_allowed(auth.rule_for(item.endpoint), identity)]


def home_url(identity):
    """Home page = first visible page; with no visible page, the no-access page."""
    items = visible_items(identity)
    return url_for(items[0].endpoint) if items else None


def template_context():
    identity = g.get('identity')
    if identity is None:
        return {}
    return {
        'identity': identity,
        'nav_items': visible_items(identity),
        'logout_url': current_app.config.get('LOGOUT_URL'),
    }

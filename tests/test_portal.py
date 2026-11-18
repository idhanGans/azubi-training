"""Candidate portal: content (overview, profile, course, modules, material) and the security check —
a candidate only reaches their own routes and never sees internal notes, other candidates or team logins."""
import json
import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from app import auth
from app.services.local_time import today

#: The ONLY endpoints a candidate may reach. New candidate routes must be deliberately
#: entered here (this test forces the check that they only deliver own data).
CANDIDATE_ENDPOINTS = {
    'me.me', 'me.ping', 'pages.home',
    'pages.my_overview', 'pages.my_profile', 'pages.my_schedule', 'pages.my_course', 'pages.my_modules',
    'pages.my_assessments', 'pages.my_progress', 'pages.my_attendance', 'pages.my_feedback', 'pages.my_reports',
    'portal.my_overview', 'portal.my_profile', 'portal.my_courses', 'portal.my_modules', 'portal.my_material_file',
    'sessions.my_schedule', 'attendance.my_attendance', 'lesson_ratings.my_lesson_ratings', 'assessments.my_assessments', 'progress.my_progress',
    'my_training.my_training', 'my_training.add_my_training', 'my_training.update_my_training',
    'pages.my_notifications', 'pages.notifications', 'notifications.list_notifications', 'notifications.count',
    'notifications.read_one', 'notifications.read_all',
}
SECRET = 'GEHEIM'


@pytest.fixture
def portal_world(as_user, grant, trainee):
    admin = as_user('root_admin')
    b1 = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    admin.post('/api/programs', json={'name': 'Sprechkurs'})
    admin.post('/api/programs', json={'name': 'Anderes Programm'})
    programs = {p['name']: p['id'] for p in admin.get('/api/programs').get_json()['programs']}
    cur = admin.post(f'/api/programs/{programs["Sprechkurs"]}/curricula', json={'level_id': b1}).get_json()['id']
    other_cur = admin.post(f'/api/programs/{programs["Anderes Programm"]}/curricula', json={'level_id': b1}).get_json()['id']
    m1, m2 = (admin.post(f'/api/curricula/{cur}/modules', json={'name': n, 'learning_objectives': ['Ziel ' + n]})
              .get_json()['id'] for n in ('Modul 1', 'Modul 2'))
    m_other = admin.post(f'/api/curricula/{other_cur}/modules', json={'name': 'Fremdes Modul'}).get_json()['id']
    pdf = admin.upload(f'/api/modules/{m1}/materials', {'type': 'PDF', 'title': 'Fragenkatalog'}, 'k.pdf', b'%PDF-1.4 x')
    other_pdf = admin.upload(f'/api/modules/{m_other}/materials', {'type': 'PDF', 'title': 'Fremd'}, 'f.pdf', b'%PDF-1.4 y')
    old_pdf = admin.upload(f'/api/modules/{m1}/materials', {'type': 'PDF', 'title': 'Alt'}, 'a.pdf', b'%PDF-1.4 z')
    admin.post(f'/api/materials/{old_pdf.get_json()["id"]}/archive')
    maria = admin.post('/api/instructors', json={'name': 'Maria Weber', 'msh_user': 'maria.login',
                                                 'level_ids': [b1]}).get_json()['id']
    grant('maria.login', 'INSTRUCTOR')
    budi = trainee('Budi', msh_user='budi', email='budi@example.org')
    dewi = trainee('Fremde Person', msh_user='dewi')
    k1 = admin.post('/api/courses', json={'name': 'Kurs Budi', 'level_id': b1, 'instructor_id': maria,
                                          'module_id': m2, 'status': 'RUNNING'}).get_json()['id']
    k2 = admin.post('/api/courses', json={'name': 'Kurs Fremd', 'level_id': b1}).get_json()['id']
    admin.post(f'/api/courses/{k1}/participants', json={'trainee_ids': [budi]})
    admin.post(f'/api/courses/{k2}/participants', json={'trainee_ids': [dewi]})
    past = (today() - timedelta(days=2)).isoformat()
    future = (today() + timedelta(days=2)).isoformat()
    s_past = admin.post('/api/sessions', json={'course_id': k1, 'date': past, 'start': '09:00', 'end': '11:00',
                                               'notes': f'{SECRET}-Terminnotiz'}).get_json()['sessions'][0]['id']
    admin.post('/api/sessions', json={'course_id': k1, 'date': future, 'start': '09:00', 'end': '11:00',
                                      'room': 'R 1.02', 'notes': f'{SECRET}-Terminnotiz'})
    admin.put(f'/api/sessions/{s_past}/attendance', json={'entries': [
        {'trainee_id': budi, 'status': 'LATE', 'minutes_late': 5, 'note': f'{SECRET}-Anwesenheit'}]})
    tpl = admin.post('/api/assessment-templates', json={'name': 'Test', 'passing_percent': 60, 'categories': [
        {'name': 'Sprechen', 'max_score': 10, 'weight': 1}]}).get_json()
    for tid, points in ((budi, 8), (dewi, 3)):
        aid = admin.post('/api/assessments', json={
            'trainee_id': tid, 'template_id': tpl['id'], 'instructor_id': maria, 'assessed_on': past,
            'scores': [{'category_id': tpl['categories'][0]['id'], 'points': points}],
            'recommendations': 'Konnektoren üben', 'internal_note': f'{SECRET}-Bewertung'}).get_json()['assessment']['id']
        admin.post(f'/api/assessments/{aid}/finalize')
    admin.post('/api/assessments', json={'trainee_id': budi, 'template_id': tpl['id'], 'instructor_id': maria,
                                         'assessed_on': past, 'internal_note': f'{SECRET}-Entwurf'})
    return {'admin': admin, 'budi': as_user('budi'), 'dewi': as_user('dewi'), 'k1': k1, 'm1': m1, 'm2': m2,
            'pdf': pdf.get_json()['id'], 'other_pdf': other_pdf.get_json()['id'],
            'old_pdf': old_pdf.get_json()['id']}


# ---------- Content ----------

def test_uebersicht_profil_kurs(portal_world):
    budi = portal_world['budi']
    ov = budi.get('/api/my-overview').get_json()
    assert ov['candidate']['name'] == 'Budi' and 'created_by' not in ov['candidate']
    assert [s['date'] for s in ov['next_sessions']] == [(today() + timedelta(days=2)).isoformat()]
    assert ov['attendance']['rate'] == 1.0
    assert ov['latest_assessment']['overall_percent'] == 80.0
    assert ov['latest_assessment']['recommendations'] == 'Konnektoren üben'
    assert ov['modules'][0]['completed'] == 1 and ov['skills'][0]['skill'] == 'SPEAKING'
    assert budi.get('/api/my-profile').get_json()['candidate']['email'] == 'budi@example.org'
    courses = budi.get('/api/my-courses').get_json()['courses']
    assert [c['name'] for c in courses] == ['Kurs Budi']
    assert courses[0]['instructor'] == {'name': 'Maria Weber'} and courses[0]['module']['name'] == 'Modul 2'
    assert courses[0]['next_sessions'][0]['room'] == 'R 1.02'


def test_heute_termine_und_tages_report(portal_world):
    """"What do I need to do today?": own sessions today (without cancelled, without others') + daily report open/done."""
    admin, budi, day = portal_world['admin'], portal_world['budi'], today().isoformat()
    assert budi.get('/api/my-overview').get_json()['today'] == {'date': day, 'sessions': [], 'report_done': False}
    ids = [admin.post('/api/sessions', json={'course_id': portal_world['k1'], 'date': day, 'start': start, 'end': end,
                                             'notes': f'{SECRET}-heute'}).get_json()['sessions'][0]['id']
           for start, end in (('07:00', '08:00'), ('20:00', '21:00'))]
    admin.patch(f'/api/sessions/{ids[0]}', json={'status': 'CANCELLED', 'cancel_reason': 'Dozentin krank'})
    assert budi.post('/api/training/me', json={'period': day, 'hours': 2, 'lang': True}).status_code == 201
    now = budi.get('/api/my-overview').get_json()['today']
    assert [s['start'] for s in now['sessions']] == ['20:00'] and now['report_done'] is True
    assert SECRET not in str(now)                                               # only public_dict, no notes
    assert portal_world['dewi'].get('/api/my-overview').get_json()['today']['sessions'] == []


def test_module_mit_stand_lernzielen_und_material(portal_world):
    cur = portal_world['budi'].get('/api/my-modules').get_json()['curricula']
    assert len(cur) == 1
    mods = cur[0]['modules']
    assert [(m['name'], m['state']) for m in mods] == [('Modul 1', 'done'), ('Modul 2', 'current')]
    assert mods[0]['learning_objectives'] == ['Ziel Modul 1']
    assert [m['title'] for m in mods[0]['materials']] == ['Fragenkatalog']          # archived one is missing
    assert set(mods[0]['materials'][0]) == {'id', 'type', 'title', 'description', 'url', 'has_file', 'file_name',
                                            'size_bytes'}
    # without a course module: no modules
    assert portal_world['dewi'].get('/api/my-modules').get_json()['curricula'] == []


def test_material_nur_aus_eigenem_curriculum(portal_world):
    budi, w = portal_world['budi'], portal_world
    res = budi.get(f'/api/my-materials/{w["pdf"]}/file')
    assert res.status_code == 200 and res.data.startswith(b'%PDF') and res.headers['X-Content-Type-Options'] == 'nosniff'
    assert budi.get(f'/api/my-materials/{w["other_pdf"]}/file').status_code == 404      # other curriculum
    assert budi.get(f'/api/my-materials/{w["old_pdf"]}/file').status_code == 404        # archived
    assert portal_world['dewi'].get(f'/api/my-materials/{w["pdf"]}/file').status_code == 404
    assert budi.get(f'/api/materials/{w["pdf"]}/file').status_code == 403                # team route stays closed


# ---------- Security ----------

def _url(rule):
    return re.sub(r'<(?:\w+:)?(\w+)>', '1', rule.rule)


def test_kandidat_erreicht_nur_kandidaten_routen(app, portal_world):
    """Every route of the app, every method: without clearance for candidates -> 403 (pages too)."""
    budi = portal_world['budi']
    open_for_candidates = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static' or rule.endpoint.startswith('msh_health.'):
            continue
        kind = getattr(app.view_functions[rule.endpoint], auth.ACCESS_ATTR)[0]
        if kind in ('candidate', 'authenticated'):
            open_for_candidates.add(rule.endpoint)
            continue
        for method in rule.methods - {'HEAD', 'OPTIONS'}:
            res = budi._call(method, _url(rule), json={} if method != 'GET' else None)
            assert res.status_code == 403, f'{method} {rule.rule} -> {res.status_code}'
    assert open_for_candidates == CANDIDATE_ENDPOINTS


def test_kandidat_sieht_nie_interne_notizen_fremde_oder_team_logins(app, portal_world):
    budi, w = portal_world['budi'], portal_world
    bodies = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint in CANDIDATE_ENDPOINTS and 'GET' in rule.methods and rule.endpoint != 'portal.my_material_file':
            res = budi.get(_url(rule), headers={'Accept': 'application/json'})
            assert res.status_code in (200, 302), rule.rule
            bodies.append(res.get_data(as_text=True))
    text = '\n'.join(bodies)
    assert SECRET not in text                       # session, attendance, assessment notes, draft
    assert 'Fremde Person' not in text and 'Kurs Fremd' not in text
    for login in ('root_admin', 'maria.login'):     # whoever created/recorded something stays internal
        assert login not in text, login
    assert '"internal_note"' not in text and '"notes"' not in text and '"note"' not in text
    my = json.loads(budi.get('/api/my-assessments').get_data(as_text=True))['assessments']
    assert len(my) == 1                              # only finalized, only own



def test_material_nur_fuer_lehrkraefte(portal_world, as_user, db):
    """Solutions/lesson plans (`team_only`): team + instructor see and download them, the candidate neither in
    "My modules" nor via the file route. Multipart sends text — "false" must not count as yes."""
    admin, budi, m1 = portal_world['admin'], portal_world['budi'], portal_world['m1']
    solution = admin.upload(f'/api/modules/{m1}/materials', {'type': 'PDF', 'title': 'Lösungen', 'team_only': 'true'},
                            'l.pdf', b'%PDF-1.4 loesung').get_json()
    plain = admin.upload(f'/api/modules/{m1}/materials', {'type': 'PDF', 'title': 'Handout', 'team_only': 'false'},
                         'h.pdf', b'%PDF-1.4 handout').get_json()
    assert (solution['team_only'], plain['team_only']) == (True, False)
    titles = [m['title'] for m in budi.get('/api/my-modules').get_json()['curricula'][0]['modules'][0]['materials']]
    assert titles == ['Fragenkatalog', 'Handout']
    assert budi.get(f'/api/my-materials/{solution["id"]}/file').status_code == 404
    assert budi.get(f'/api/my-materials/{plain["id"]}/file').status_code == 200
    maria = as_user('maria.login')                                                    # instructor: sees everything
    assert [m['title'] for m in maria.get(f'/api/modules/{m1}').get_json()['materials']] == [
        'Fragenkatalog', 'Lösungen', 'Handout']
    assert maria.get(f'/api/materials/{solution["id"]}/file').data == b'%PDF-1.4 loesung'
    # toggle via JSON, with old/new in the activity log; nonsense -> 400
    assert admin.patch(f'/api/materials/{plain["id"]}', json={'team_only': True}).get_json()['team_only'] is True
    assert budi.get(f'/api/my-materials/{plain["id"]}/file').status_code == 404
    entry = db.session.execute(text("SELECT detail FROM activity_log WHERE action = 'material.update' "
                                       "ORDER BY id DESC LIMIT 1")).scalar()
    assert entry['changes']['team_only'] == [False, True]
    res = admin.patch(f'/api/materials/{plain["id"]}', json={'team_only': 'vielleicht'})
    assert res.status_code == 400 and res.get_json()['field'] == 'team_only'

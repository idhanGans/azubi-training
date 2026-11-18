"""/docs-Eintraege fuer Dozenten, Kurse, Stundenplan (Termine) und „Mein Unterricht"."""
_LEVEL = {'id': 3, 'code': 'B1', 'name': 'B1'}
_I = {'id': 1, 'name': 'Maria Weber', 'email': 'maria.weber@example.de', 'msh_user': 'maria_weber',
      'qualification': 'DaF-Lehrerin, Goethe-Prüferin B1/B2', 'specialization': 'Prüfungsvorbereitung',
      'levels': [_LEVEL], 'availability': [{'weekday': 0, 'start': '08:00', 'end': '16:00'}],
      'status': 'ACTIVE', 'archived_at': None}
_IW = {'name': 'Maria Weber', 'email': 'maria.weber@example.de', 'msh_user': 'maria_weber', 'level_ids': [3],
       'availability': [{'weekday': 0, 'start': '08:00', 'end': '16:00'}], 'status': 'ACTIVE'}
_K = {'id': 1, 'name': 'B1 – Gruppe Herbst 2026', 'description': None, 'level_id': 3, 'level': _LEVEL,
      'module_id': 8, 'module': {'id': 8, 'name': 'Modul 8 – Konjunktiv II', 'program': 'Deutschsprachkurs'},
      'instructor_id': 1, 'instructor': {'id': 1, 'name': 'Maria Weber', 'status': 'ACTIVE', 'archived': False},
      'status': 'RUNNING', 'archived_at': None}
_T = {'id': 5, 'candidate_no': 'K-00005', 'name': 'Budi Santoso', 'current_level': _LEVEL,
      'status': {'id': 3, 'code': 'LANGUAGE_COURSE', 'name': 'Im Sprachkurs'}}

_S = {'id': 7, 'date': '2026-09-25', 'start': '10:00', 'end': '12:00', 'starts_at': '2026-09-25T08:00:00+00:00',
      'ends_at': '2026-09-25T10:00:00+00:00', 'duration_minutes': 120,
      'course': {'id': 1, 'name': _K['name'], 'level': _LEVEL}, 'module': {'id': 8, 'name': 'Modul 8 – Konjunktiv II'},
      'instructor': _K['instructor'], 'room': 'R 2.14', 'location': 'Berlin, Schulstraße 1', 'online_url': None,
      'status': 'SCHEDULED', 'cancel_reason': None}
_SI = {**_S, 'course_id': 1, 'module_id': 8, 'instructor_id': 1, 'notes': 'Bitte Wörterbuch mitbringen',
       'attendance_from': '2026-09-25T07:45:00+00:00'}   # ab hier Anwesenheit erfassbar
_CONFLICT = {'error': 'Zeitkonflikt erkannt. Der Dozent ist zu diesem Zeitpunkt bereits eingeplant. '
                      '(A2 – Abendkurs, 25.09.2026 11:00–12:30 Uhr)', 'field': 'instructor_id',
             'details': {'kind': 'instructor', 'sessions': [{'session_id': 3, 'course': 'A2 – Abendkurs',
                                                             'date': '2026-09-25', 'start': '11:00', 'end': '12:30'}]}}


def _e(method, path, description, response, request=None):
    entry = {'path': path, 'method': method, 'description': description, 'response_example': response}
    if request is not None:
        entry['request_example'] = request
    return entry


DOCS = [
    _e('GET', '/api/instructors', 'Dozenten (?archived=1 archivierte) mit Kursanzahl und Hinweis, ob der Login '
       'die Rolle DOZENT hat — instructor.view',
       {'instructors': [{**_I, 'course_count': 2, 'has_instructor_role': True}]}),
    _e('POST', '/api/instructors', 'Dozent anlegen (Verfügbarkeit: je Wochentag 0=Mo…6=So ein Fenster; '
       'Login nie zugleich Kandidat, 409) — instructor.manage', _I, _IW),
    _e('GET', '/api/instructors/<id>', 'Dozent mit seinen Kursen — instructor.view',
       {'instructor': {**_I, 'course_count': 1, 'has_instructor_role': True}, 'courses': [_K]}),
    _e('PATCH', '/api/instructors/<id>', 'Dozent bearbeiten (nur mitgeschickte Felder) — instructor.manage', _I,
       {'status': 'ON_LEAVE'}),
    _e('POST', '/api/instructors/<id>/archive', 'Archivieren (409, solange geplante/laufende Kurse zugeordnet '
       'sind) — instructor.manage', {**_I, 'archived_at': '2026-09-23T10:00:00+00:00'}, {}),
    _e('POST', '/api/instructors/<id>/restore', 'Archivierten Dozenten wiederherstellen — instructor.manage', _I, {}),
    _e('GET', '/api/courses', 'Kurse (?archived=1, level_id, instructor_id, status=PLANNED|RUNNING|COMPLETED) '
       'mit Teilnehmerzahl — schedule.view; Dozenten: nur eigene', {'courses': [{**_K, 'participant_count': 12}]}),
    _e('POST', '/api/courses', 'Kurs anlegen; Modul muss zum Niveau gehören, Dozent aktiv sein und das Niveau '
       'unterrichten (sonst 409) — schedule.create', _K,
       {'name': 'B1 – Gruppe Herbst 2026', 'level_id': 3, 'module_id': 8, 'instructor_id': 1, 'status': 'PLANNED'}),
    _e('GET', '/api/courses/<id>', 'Kurs mit Teilnehmern — schedule.view; Dozenten: nur eigene (sonst 404)',
       {'course': _K, 'participants': [{**_T, 'added_at': '2026-09-23T10:00:00+00:00', 'attendance': {
           'present': 8, 'late': 1, 'excused': 0, 'absent': 1, 'recorded': 10, 'rate': 0.9}}]}),
    _e('PATCH', '/api/courses/<id>', 'Kurs bearbeiten, Dozent/Modul zuordnen — schedule.edit', _K,
       {'instructor_id': 1}),
    _e('POST', '/api/courses/<id>/participants', 'Kandidaten aufnehmen (vorhandene werden übersprungen) — '
       'schedule.edit', {'added': [5, 6]}, {'trainee_ids': [5, 6]}),
    _e('DELETE', '/api/courses/<id>/participants/<tid>', 'Kandidaten aus dem Kurs nehmen (protokolliert) — '
       'schedule.edit', {'removed': 5}, {}),
    _e('POST', '/api/courses/<id>/archive', 'Kurs archivieren — schedule.edit',
       {**_K, 'archived_at': '2026-09-23T10:00:00+00:00'}, {}),
    _e('POST', '/api/courses/<id>/restore', 'Archivierten Kurs wiederherstellen (409 bei Namensgleichheit) — '
       'schedule.edit', _K, {}),
    _e('GET', '/api/modules', 'Nicht archivierte Module aller Curricula eines Niveaus (?level_id=) — curriculum.view',
       {'modules': [{'id': 8, 'name': 'Modul 8 – Konjunktiv II', 'program': 'Deutschsprachkurs', 'level': _LEVEL}]}),
    _e('GET', '/api/sessions', 'Termine im Zeitraum ?from=&to= (Ortszeit, max. 63 Tage); Filter course_id, '
       'instructor_id, trainee_id, level_id, module_id, include_cancelled=1 — schedule.view; Dozenten: nur eigene Kurse',
       {'sessions': [{**_SI, 'participant_count': 12}]}),
    _e('POST', '/api/sessions', 'Termin(e) anlegen: Datum + Beginn/Ende in Ortszeit der Schule (ENV SCHOOL_TZ, hier WIB), optional '
       'repeat_until = wöchentlich bis (max. 52); Dozent/Modul Vorgabe vom Kurs. 409 bei Zeitkonflikt '
       '(Dozent oder Kandidat bereits eingeplant, mit `details`); `warnings` = außerhalb der Verfügbarkeit '
       '— schedule.create', {'sessions': [_SI], 'warnings': []},
       {'course_id': 1, 'date': '2026-09-25', 'start': '10:00', 'end': '12:00', 'room': 'R 2.14',
        'repeat_until': '2026-12-18'}),
    _e('GET', '/api/sessions/<id>', 'Ein Termin — schedule.view', {'session': {**_SI, 'participant_count': 12}}),
    _e('PATCH', '/api/sessions/<id>', 'Termin verschieben/ändern, Dozent/Modul zuordnen, absagen '
       '(status=CANCELLED + cancel_reason) oder reaktivieren; Konfliktprüfung wie beim Anlegen — schedule.edit',
       {'session': _SI, 'warnings': []}, {'date': '2026-09-26', 'start': '09:00', 'end': '11:00'}),
    _e('GET', '/api/my-schedule', 'Kandidat: eigene Termine (Default: heute + 27 Tage, sonst ?from=&to=), '
       'ohne interne Notizen', {'sessions': [_S]}),
    _e('GET', '/api/my-teaching', 'Dozent: heutige + kommende Termine (14 Tage), Unterrichtszeit im Monat (Stunden), Termine der letzten 14 Tage ohne vollständige Anwesenheit, eigene Kurse, deren Teilnehmer (nur mit verknüpftem '
       'Dozenten-Datensatz)',
       {'instructor': _I, 'stats': {'course_count': 1, 'running_count': 1, 'participant_count': 12, 'today_count': 1,
                                    'hours_month': 24.0, 'open_attendance_count': 1},
        'windows': {'upcoming_days': 14, 'open_attendance_days': 14},
        'open_attendance': [_SI],
        'today': [_SI], 'upcoming': [_SI], 'courses': [{**_K, 'participant_count': 12}], 'participants': [{**_T, 'courses': [{'id': 1, 'name': _K['name']}]}]}),
]

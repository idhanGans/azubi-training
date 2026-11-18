"""/docs-Eintraege der Kandidaten-API (eigene Datei, damit routes/candidates.py kurz bleibt)."""
_C = {'id': 1, 'candidate_no': 'K-00001', 'name': 'Budi Santoso', 'fach': 'Elektro',
      'status': {'id': 3, 'code': 'LANGUAGE_COURSE', 'name': 'Im Sprachkurs'},
      'current_level': {'id': 2, 'code': 'A2', 'name': 'A2'},
      'target_level': {'id': 3, 'code': 'B1', 'name': 'B1'},
      'start_date': '2026-09-01', 'expected_completion_date': '2027-03-31', 'archived_at': None}
_K = {'id': 1, 'name': 'B1 – Gruppe Herbst 2026', 'status': 'RUNNING',
      'instructor': {'id': 1, 'name': 'Maria Weber', 'status': 'ACTIVE', 'archived': False}}
_W = {'name': 'Budi Santoso', 'fach': 'Elektro', 'status_id': 3, 'current_level_id': 2,
      'target_level_id': 3, 'start_date': '2026-09-01', 'msh_user': 'budi_santoso'}

DOCS = [
    {'path': '/api/candidates', 'method': 'GET',
     'description': 'Kandidatenliste — ?q= (Name/Nr./E-Mail/Login), status_id, level_id, fach, archived=1, '
                    'sort=name|candidate_no|status|level|last_rating|last_report (mit - absteigend), '
                    'page, per_page (max 100) — candidate.view; Dozenten: nur Teilnehmer eigener Kurse',
     'response_example': {'items': [{**_C, 'last_rating_at': None, 'last_report_at': None, 'courses': [_K],
                                    'attendance_rate': 0.94}],
                          'total': 1, 'page': 1, 'per_page': 25}},
    {'path': '/api/candidates', 'method': 'POST',
     'description': 'Kandidat anlegen (Kandidaten-Nr. vergibt die DB; 400 ungültig, 409 Login vergeben) — candidate.create',
     'request_example': _W, 'response_example': _C},
    {'path': '/api/candidates/<id>', 'method': 'GET',
     'description': 'Kandidatenprofil: Stammdaten, Kurse, nächste 5 Termine, Trainings-Kennzahlen; `ratings` nur mit assessment.view, `attendance` nur mit attendance.view '
                    '— candidate.view; Dozenten: nur Teilnehmer eigener Kurse (sonst 404)',
     'response_example': {'candidate': _C, 'courses': [_K], 'upcoming_sessions': [], 'ratings': [],
                          'attendance': {'stats': {'present': 15, 'late': 2, 'excused': 1, 'absent': 1, 'recorded': 19,
                                                   'rate': 0.9444}, 'recent': []},
                          'training': {'report_count': 0, 'hours_total': 0, 'recent_reports': []}}},
    {'path': '/api/candidates/<id>', 'method': 'PATCH',
     'description': 'Kandidat bearbeiten (nur mitgeschickte Felder) — candidate.edit',
     'request_example': {'status_id': 4, 'current_level_id': 3}, 'response_example': _C},
    {'path': '/api/candidates/<id>/archive', 'method': 'POST',
     'description': 'Archivieren (ersetzt Löschen; Historie bleibt, Portal-Zugang gesperrt) — candidate.edit',
     'request_example': {}, 'response_example': {**_C, 'archived_at': '2026-09-23T10:00:00+00:00'}},
    {'path': '/api/candidates/<id>/restore', 'method': 'POST',
     'description': 'Archivierten Kandidaten wiederherstellen — candidate.edit',
     'request_example': {}, 'response_example': _C},
]

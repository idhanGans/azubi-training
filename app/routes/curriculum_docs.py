"""/docs-Eintraege fuer Programme, Curricula, Module und Lernmaterial."""
_P = {'id': 1, 'name': 'Deutschsprachkurs', 'description': None, 'active': True}
_C = {'id': 1, 'program_id': 1, 'program': 'Deutschsprachkurs', 'level': {'id': 3, 'code': 'B1', 'name': 'B1'},
      'description': None, 'status': 'ACTIVE'}
_M = {'id': 8, 'curriculum_id': 1, 'name': 'Modul 8 – Konjunktiv II', 'position': 8, 'duration_hours': 12.0,
      'learning_objectives': ['Wünsche formulieren', 'Höfliche Bitten formulieren'], 'status': 'ACTIVE'}
_F = {'id': 1, 'module_id': 8, 'type': 'PDF', 'title': 'Arbeitsblatt', 'url': None, 'has_file': True,
      'file_name': 'konjunktiv.pdf', 'content_type': 'application/pdf', 'size_bytes': 48213, 'team_only': False,
      'archived_at': None}
_UPLOAD = {'_note': 'multipart/form-data mit Feld `file` + Header X-Requested-With: fetch'}


def _e(method, path, description, response, request=None):
    entry = {'path': path, 'method': method, 'description': description, 'response_example': response}
    if request is not None:
        entry['request_example'] = request
    return entry


DOCS = [
    _e('GET', '/api/programs', 'Programme mit ihren Curricula (je Niveau: Status, Anzahl Module, Stunden) — curriculum.view',
       {'programs': [{**_P, 'curricula': [{**_C, 'module_count': 12, 'hours_total': 96.0}]}]}),
    _e('POST', '/api/programs', 'Programm anlegen (409 Name vergeben) — curriculum.create', _P,
       {'name': 'Deutschsprachkurs', 'description': '…'}),
    _e('PATCH', '/api/programs/<id>', 'Programm bearbeiten/deaktivieren — curriculum.edit', _P,
       {'description': '…', 'active': True}),
    _e('POST', '/api/programs/<id>/curricula', 'Sprachniveau ins Programm aufnehmen = Curriculum anlegen '
       '(je Niveau eines, sonst 409) — curriculum.create', _C, {'level_id': 3}),
    _e('GET', '/api/curricula/<id>', 'Curriculum (+ Anzahl aktiver Module, Stunden gesamt) mit Modulen in Reihenfolge '
       '(+ Anzahl Materialien) — curriculum.view',
       {'curriculum': {**_C, 'module_count': 12, 'hours_total': 96.0}, 'modules': [{**_M, 'material_count': 2}]}),
    _e('PATCH', '/api/curricula/<id>', 'Beschreibung/Status (DRAFT|ACTIVE|ARCHIVED) — curriculum.edit', _C,
       {'status': 'ACTIVE'}),
    _e('POST', '/api/curricula/<id>/modules', 'Modul anlegen (wird hinten angehängt) — curriculum.create', _M,
       {'name': 'Modul 8 – Konjunktiv II', 'duration_hours': 12, 'learning_objectives': ['Wünsche formulieren']}),
    _e('PUT', '/api/curricula/<id>/module-order', 'Modul-Reihenfolge setzen (alle IDs genau einmal) — curriculum.edit',
       {'module_ids': [3, 1, 2]}, {'module_ids': [3, 1, 2]}),
    _e('GET', '/api/modules/<id>', 'Modul mit Lernzielen + Materialien (?archived=1 inkl. archivierter) — curriculum.view',
       {'module': _M, 'curriculum': _C, 'materials': [_F],
        'upload_rules': {'extensions': {'PDF': ['pdf'], 'LINK': []}, 'max_mb': 50}}),
    _e('PATCH', '/api/modules/<id>', 'Modul bearbeiten (Name, Beschreibung, Dauer, Lernziele, Status) — curriculum.edit',
       _M, {'learning_objectives': ['Wünsche formulieren', 'Irreale Situationen beschreiben']}),
    _e('PUT', '/api/modules/<id>/material-order', 'Reihenfolge der aktiven Materialien setzen — curriculum.edit',
       {'material_ids': [2, 1]}, {'material_ids': [2, 1]}),
    _e('POST', '/api/modules/<id>/materials', 'Material anlegen: JSON (Link) oder multipart mit Datei; '
       'Art PDF|VIDEO|DOCUMENT|LINK|IMAGE|EXERCISE|HOMEWORK; Endung + Inhalt werden geprueft; `team_only` = nur '
       'Lehrkräfte (Kandidaten sehen es nie) — curriculum.create',
       _F, {'type': 'LINK', 'title': 'Erklärvideo', 'url': 'https://www.youtube.com/watch?v=…', 'team_only': False}),
    _e('PATCH', '/api/materials/<id>', 'Titel/Beschreibung/Link/`team_only` ändern (Art ist fest) — curriculum.edit', _F,
       {'title': 'Lösungen Konjunktiv II', 'team_only': True}),
    _e('POST', '/api/materials/<id>/file', 'Datei ersetzen (alte bleibt erhalten, Protokoll mit Hash) — curriculum.edit',
       _F, _UPLOAD),
    _e('POST', '/api/materials/<id>/archive', 'Material archivieren — curriculum.edit', {**_F, 'archived_at': '…'}, {}),
    _e('POST', '/api/materials/<id>/restore', 'Archiviertes Material wiederherstellen — curriculum.edit', _F, {}),
    _e('GET', '/api/materials/<id>/file', 'Datei herunterladen/anzeigen (PDF/Bilder inline, sonst Download; '
       'nosniff) — curriculum.view', '<Datei-Inhalt> (Content-Type der Datei)'),
]

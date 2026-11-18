"""Lernmaterial: Link oder Datei, Dateipruefung, sicherer Download, Archiv."""
import hashlib

import pytest

PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 20


@pytest.fixture
def module_id(as_user):
    admin = as_user('root_admin')
    level = next(e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries'] if e['code'] == 'B1')
    pid = admin.post('/api/programs', json={'name': 'Deutschsprachkurs'}).get_json()['id']
    cid = admin.post(f'/api/programs/{pid}/curricula', json={'level_id': level}).get_json()['id']
    return admin.post(f'/api/curricula/{cid}/modules', json={'name': 'Modul 8'}).get_json()['id']


def test_pdf_hochladen_und_herunterladen(as_user, grant, module_id):
    admin = as_user('root_admin')
    res = admin.upload(f'/api/modules/{module_id}/materials', {'type': 'PDF', 'title': 'Arbeitsblatt'},
                       '../../etc/Konjunktiv II.pdf', PDF)
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert (body['file_name'], body['size_bytes'], body['has_file']) == ('Konjunktiv II.pdf', len(PDF), True)
    grant('dozent', 'INSTRUCTOR')
    dl = as_user('dozent').get(f'/api/materials/{body["id"]}/file')
    assert dl.status_code == 200 and dl.data == PDF
    assert dl.headers['Content-Type'] == 'application/pdf'
    assert dl.headers['X-Content-Type-Options'] == 'nosniff'
    assert dl.headers['Content-Disposition'].startswith('inline')
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert log['detail']['sha256'] == hashlib.sha256(PDF).hexdigest()


def test_nicht_inline_dateien_kommen_als_download_in_sandbox(as_user, module_id):
    admin = as_user('root_admin')
    mid = admin.upload(f'/api/modules/{module_id}/materials', {'type': 'DOCUMENT', 'title': 'Vokabeln'},
                       'vokabeln.txt', 'der Wunsch – die Wünsche\n'.encode()).get_json()['id']
    dl = admin.get(f'/api/materials/{mid}/file')
    assert dl.headers['Content-Disposition'].startswith('attachment')
    assert "sandbox" in dl.headers['Content-Security-Policy']


@pytest.mark.parametrize('kind,name,content,feld', [
    ('PDF', 'boese.exe', b'MZ\x90\x00', 'file'),            # Endung nicht erlaubt
    ('PDF', 'getarnt.pdf', b'MZ\x90\x00binary', 'file'),     # Inhalt passt nicht zur Endung
    ('IMAGE', 'bild.svg', b'<svg onload=alert(1)>', 'file'), # SVG nie erlaubt
    ('DOCUMENT', 'seite.html', b'<script>x</script>', 'file'),
    ('PDF', 'leer.pdf', b'', 'file'),
    ('PDF', 'gross.pdf', b'%PDF-' + b'x' * (1024 * 1024 + 10), 'file'),   # MAX_UPLOAD_MB=1 im Test
])
def test_unerlaubte_dateien(as_user, module_id, kind, name, content, feld):
    res = as_user('root_admin').upload(f'/api/modules/{module_id}/materials', {'type': kind, 'title': 'x'},
                                       name, content)
    assert res.status_code in (400, 413) and res.get_json()['field'] == feld, res.get_json()


def test_abgelehnte_datei_bleibt_nicht_liegen(app, as_user, module_id):
    import os
    root = app.config['UPLOAD_DIR']
    before = sum(len(files) for _, _, files in os.walk(root))
    as_user('root_admin').upload(f'/api/modules/{module_id}/materials', {'type': 'PDF', 'title': 'x'},
                                 'getarnt.pdf', b'MZ\x90\x00binary')
    assert sum(len(files) for _, _, files in os.walk(root)) == before


@pytest.mark.parametrize('payload,feld', [
    ({'type': 'LINK', 'title': 'Video'}, 'url'),
    ({'type': 'LINK', 'title': 'Video', 'url': 'javascript:alert(1)'}, 'url'),
    ({'type': 'PDF', 'title': 'Blatt'}, 'file'),
    ({'type': 'PDF', 'title': 'Blatt', 'url': 'https://example.org/a.pdf'}, 'file'),
    ({'type': 'HOMEWORK', 'title': 'Aufgabe'}, 'description'),
    ({'type': 'FOTO', 'title': 'x'}, 'type'),
])
def test_link_material_pruefungen(as_user, module_id, payload, feld):
    res = as_user('root_admin').post(f'/api/modules/{module_id}/materials', json=payload)
    assert res.status_code == 400 and res.get_json()['field'] == feld


def test_link_und_hausaufgabe_ohne_datei(as_user, module_id):
    admin = as_user('root_admin')
    assert admin.post(f'/api/modules/{module_id}/materials', json={
        'type': 'VIDEO', 'title': 'Erklärvideo', 'url': 'https://www.youtube.com/watch?v=abc'}).status_code == 201
    hw = admin.post(f'/api/modules/{module_id}/materials', json={
        'type': 'HOMEWORK', 'title': 'Aufgabe 3', 'description': 'Schreiben Sie fünf Wünsche im Konjunktiv II.'})
    assert hw.status_code == 201
    assert admin.get(f'/api/materials/{hw.get_json()["id"]}/file').status_code == 404


def test_upload_ohne_fetch_header_ist_csrf_geschuetzt(as_user, module_id):
    res = as_user('root_admin').upload(f'/api/modules/{module_id}/materials', {'type': 'PDF', 'title': 'x'},
                                       'a.pdf', PDF, csrf_header=False)
    assert res.status_code == 415


def test_datei_ersetzen_behaelt_historie(as_user, module_id):
    admin = as_user('root_admin')
    mid = admin.upload(f'/api/modules/{module_id}/materials', {'type': 'IMAGE', 'title': 'Tafelbild'},
                       'alt.png', PNG).get_json()['id']
    res = admin.upload(f'/api/materials/{mid}/file', {}, 'neu.png', PNG + b'neu')
    assert res.status_code == 200 and res.get_json()['file_name'] == 'neu.png'
    log = admin.get('/api/activity').get_json()['activity'][0]
    assert (log['action'], log['detail']['old']['file_name']) == ('material.file', 'alt.png')
    assert admin.get(f'/api/materials/{mid}/file').data == PNG + b'neu'


def test_archivieren_reihenfolge_und_rechte(as_user, grant, trainee, module_id):
    admin = as_user('root_admin')
    ids = [admin.post(f'/api/modules/{module_id}/materials', json={
        'type': 'LINK', 'title': f'Link {i}', 'url': f'https://example.org/{i}'}).get_json()['id'] for i in range(3)]
    admin.put(f'/api/modules/{module_id}/material-order', json={'material_ids': ids[::-1]})
    admin.post(f'/api/materials/{ids[0]}/archive')
    titles = [m['title'] for m in admin.get(f'/api/modules/{module_id}').get_json()['materials']]
    assert titles == ['Link 2', 'Link 1']
    assert len(admin.get(f'/api/modules/{module_id}?archived=1').get_json()['materials']) == 3
    grant('dozent', 'INSTRUCTOR')
    assert as_user('dozent').post(f'/api/materials/{ids[1]}/archive').status_code == 403
    trainee('Anna', msh_user='anna')
    assert as_user('anna').get(f'/api/modules/{module_id}').status_code == 403

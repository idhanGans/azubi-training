"""Lernmaterial: Felder + Vollstaendigkeit pruefen, Dateien sicher ablegen."""
import unicodedata

from app.models.material import FILE_REQUIRED, TYPES, URL_REQUIRED
from app.services import file_types, validation as v
from app.services.file_store import TooLarge

TYPE_LABELS = {'PDF': 'PDF', 'VIDEO': 'Video', 'DOCUMENT': 'Dokument', 'LINK': 'Link',
               'IMAGE': 'Bild', 'EXERCISE': 'Übung', 'HOMEWORK': 'Hausaufgabe'}


def read_fields(data, material=None):
    has = (lambda key: key in data) if material else (lambda key: True)
    values = {}
    if material is None:
        if data.get('type') not in TYPES:
            raise v.ValidationError('Bitte eine gültige Art auswählen.', 'type')
        values['type'] = data['type']
    elif 'type' in data and data['type'] != material.type:
        raise v.ValidationError('Die Art eines Materials kann nachträglich nicht geändert werden.', 'type')
    if has('title'):
        values['title'] = v.text(data, 'title', 'Titel', 200, required=True)
    if has('description'):
        values['description'] = v.text(data, 'description', 'Beschreibung', 4000)
    if has('url'):
        values['url'] = v.url(data, 'url', 'Link')
    if has('team_only'):
        values['team_only'] = v.flag(data, 'team_only', 'Nur für Lehrkräfte')
    return values


def check_complete(kind, url, has_file, description):
    """Link ODER Datei — je nach Art Pflicht oder wahlweise."""
    label = TYPE_LABELS[kind]
    if url and has_file:
        raise v.ValidationError('Bitte entweder einen Link ODER eine Datei angeben, nicht beides.', 'url')
    if kind in URL_REQUIRED and not url:
        raise v.ValidationError('Für einen Link bitte die Adresse angeben.', 'url')
    if kind in FILE_REQUIRED and not has_file:
        raise v.ValidationError(f'Für „{label}“ bitte eine Datei hochladen.', 'file')
    if kind in FILE_REQUIRED and url:
        raise v.ValidationError(f'„{label}“ ist eine Datei, kein Link.', 'url')
    if kind == 'VIDEO' and not (url or has_file):
        raise v.ValidationError('Für ein Video bitte einen Link angeben oder eine Datei hochladen.', 'url')
    if kind in ('EXERCISE', 'HOMEWORK') and not (url or has_file or description):
        raise v.ValidationError(f'Für „{label}“ bitte eine Beschreibung, einen Link oder eine Datei angeben.',
                                'description')


def _clean_name(name):
    name = unicodedata.normalize('NFC', (name or '').replace('\\', '/').rsplit('/', 1)[-1])
    name = ''.join(ch for ch in name if ch.isprintable()).strip()
    return name[:255] or 'datei'


def store_upload(upload, kind, store, max_bytes):
    """Datei pruefen + ablegen. Liefert die Material-Dateifelder."""
    name = _clean_name(upload.filename)
    ext = file_types.extension(name)
    allowed = file_types.ALLOWED_BY_TYPE[kind]
    if ext not in allowed:
        raise v.ValidationError(
            f'Dateityp „.{ext or "?"}“ ist für „{TYPE_LABELS[kind]}“ nicht erlaubt. '
            f'Erlaubt: {", ".join("." + e for e in allowed)}.', 'file')
    try:
        stored = store.save(upload.stream, max_bytes)
    except TooLarge:
        raise v.ValidationError(f'Die Datei ist zu groß (höchstens {max_bytes // (1024 * 1024)} MB).',
                                'file') from None
    if stored.size == 0 or not file_types.matches_signature(file_types.KINDS[ext], store.head(stored.key)):
        store.delete(stored.key)
        raise v.ValidationError(f'Der Inhalt der Datei passt nicht zur Endung „.{ext}“.', 'file')
    return {'storage_key': stored.key, 'file_name': name, 'content_type': file_types.KINDS[ext].content_type,
            'size_bytes': stored.size, 'sha256': stored.sha256}

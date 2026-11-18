"""Welche Dateien als Lernmaterial erlaubt sind — geprueft an Endung UND Inhalt.

Kein HTML/SVG/Skript: solche Dateien koennten beim Oeffnen im Browser Code
ausfuehren. Die Magic-Bytes verhindern, dass eine umbenannte Datei durchrutscht.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FileKind:
    content_type: str
    magic: tuple          # erlaubte Anfaenge (bytes); () = Textdatei ohne Signatur
    offset: int = 0       # ab welchem Byte die Signatur steht (mp4/m4a: 4)
    inline: bool = False  # darf im Browser angezeigt werden (PDF, Bilder)


_ZIP = (b'PK\x03\x04',)
KINDS = {
    'pdf': FileKind('application/pdf', (b'%PDF-',), inline=True),
    'png': FileKind('image/png', (b'\x89PNG\r\n\x1a\n',), inline=True),
    'jpg': FileKind('image/jpeg', (b'\xff\xd8\xff',), inline=True),
    'jpeg': FileKind('image/jpeg', (b'\xff\xd8\xff',), inline=True),
    'webp': FileKind('image/webp', (b'RIFF',), inline=True),
    'docx': FileKind('application/vnd.openxmlformats-officedocument.wordprocessingml.document', _ZIP),
    'xlsx': FileKind('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', _ZIP),
    'pptx': FileKind('application/vnd.openxmlformats-officedocument.presentationml.presentation', _ZIP),
    'odt': FileKind('application/vnd.oasis.opendocument.text', _ZIP),
    'txt': FileKind('text/plain; charset=utf-8', ()),
    'mp3': FileKind('audio/mpeg', (b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2')),
    'm4a': FileKind('audio/mp4', (b'ftyp',), offset=4),
    'mp4': FileKind('video/mp4', (b'ftyp',), offset=4),
}

_DOCS = ('pdf', 'docx', 'xlsx', 'pptx', 'odt', 'txt')
_AUDIO = ('mp3', 'm4a')
ALLOWED_BY_TYPE = {
    'PDF': ('pdf',),
    'IMAGE': ('png', 'jpg', 'jpeg', 'webp'),
    'DOCUMENT': _DOCS + _AUDIO,
    'VIDEO': ('mp4',),
    'EXERCISE': _DOCS + _AUDIO + ('png', 'jpg', 'jpeg', 'webp'),
    'HOMEWORK': _DOCS + _AUDIO + ('png', 'jpg', 'jpeg', 'webp'),
    'LINK': (),
}


def extension(file_name):
    return file_name.rsplit('.', 1)[-1].lower() if '.' in (file_name or '') else ''


def matches_signature(kind, head):
    if not kind.magic:
        return b'\x00' not in head   # Text: keine Binaerdaten
    return any(head[kind.offset:].startswith(sig) for sig in kind.magic)

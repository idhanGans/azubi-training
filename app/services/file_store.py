"""Datei-Ablage fuer Lernmaterial (lokales Volume, `UPLOAD_DIR`).

Dateien liegen unter einem zufaelligen Schluessel (32 Hex-Zeichen) — der
Original-Name steht nur in der DB. Ausgeliefert wird ausschliesslich ueber die
Route mit Rechte-Pruefung. Diese Klasse ist die EINZIGE Stelle, die das
Dateisystem kennt; ein Wechsel auf den Plattform-S3-Proxy (`s3-api`) tauscht
nur sie aus.
"""
import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

_KEY = re.compile(r'^[0-9a-f]{32}$')
_CHUNK = 64 * 1024


class TooLarge(ValueError):
    pass


@dataclass(frozen=True)
class StoredFile:
    key: str
    size: int
    sha256: str


class FileStore:
    def __init__(self):
        self.root = None

    def init_app(self, app):
        self.root = Path(app.config['UPLOAD_DIR'])

    def _path(self, key):
        if not _KEY.match(key or ''):
            raise ValueError('ungueltiger Datei-Schluessel')
        return self.root / key[:2] / key

    def save(self, stream, max_bytes):
        """Stream schreiben (atomar ueber .part + rename), Groesse begrenzen."""
        key = uuid.uuid4().hex
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix('.part')
        digest, size = hashlib.sha256(), 0
        try:
            with open(partial, 'wb') as out:
                while chunk := stream.read(_CHUNK):
                    size += len(chunk)
                    if size > max_bytes:
                        raise TooLarge()
                    digest.update(chunk)
                    out.write(chunk)
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)
        return StoredFile(key=key, size=size, sha256=digest.hexdigest())

    def head(self, key, length=16):
        with open(self._path(key), 'rb') as fh:
            return fh.read(length)

    def open(self, key):
        return open(self._path(key), 'rb')

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)

"""Review-Notizen der Gesamtbewertung: eine freie Notiz je Azubi an festen 2-Wochen-Stichtagen.

Die Stichtage sind feste Kalendertage ab `START` im 14-Tage-Takt bis einschliesslich `END` — sie
verschieben sich NICHT mit dem heutigen Datum. Schreiben darf nur `note.edit` (Super-Admin); lesen
jeder, der die Rangliste sieht. Leerer Text loescht die Zeile (kein Eintrag = keine Notiz).
"""
from datetime import date, timedelta

from app.extensions import db
from app.models.common import iso, utcnow
from app.models.trainee_note import TraineeNote

START = date(2026, 10, 19)        # erster Stichtag (Projektvorgabe „ab heute")
END = date(2026, 12, 31)          # letzter Stichtag spaetestens Ende Dezember
STEP = timedelta(days=14)         # alle zwei Wochen
MAX_CHARS = 2000


def checkpoints():
    """Feste Stichtage als date-Liste (START, START+14, … <= END)."""
    days, day = [], START
    while day <= END:
        days.append(day)
        day += STEP
    return days


def checkpoints_iso():
    return [d.isoformat() for d in checkpoints()]


def for_trainees(ids):
    """{trainee_id: {stichtag_iso: text}} fuer die gegebenen Azubis."""
    result = {}
    if not ids:
        return result
    for note in TraineeNote.query.filter(TraineeNote.trainee_id.in_(ids)):
        result.setdefault(note.trainee_id, {})[note.checkpoint.isoformat()] = note.text
    return result


def set_note(trainee_id, checkpoint_iso, text, username):
    """Notiz setzen/aktualisieren; leerer Text loescht sie. Gibt den neuen Stand zurueck (ohne commit)."""
    day = date.fromisoformat(checkpoint_iso)
    note = TraineeNote.query.filter_by(trainee_id=trainee_id, checkpoint=day).first()
    text = (text or '').strip()
    if not text:
        if note is not None:
            db.session.delete(note)
        return {'trainee_id': trainee_id, 'checkpoint': checkpoint_iso, 'text': '',
                'updated_by': username, 'updated_at': None}
    if note is None:
        note = TraineeNote(trainee_id=trainee_id, checkpoint=day)
        db.session.add(note)
    note.text = text
    note.updated_by = username
    note.updated_at = utcnow()
    db.session.flush()
    return {'trainee_id': trainee_id, 'checkpoint': checkpoint_iso, 'text': note.text,
            'updated_by': note.updated_by, 'updated_at': iso(note.updated_at)}


def attach(body, identity):
    """Rangliste-Antwort um Stichtage, Schreibrecht und die Notizen je Zeile ergaenzen."""
    body['note_checkpoints'] = checkpoints_iso()
    body['can_edit_notes'] = identity.can('note.edit')
    notes = for_trainees([r['id'] for r in body['rows']])
    for row in body['rows']:
        row['notes'] = notes.get(row['id'], {})

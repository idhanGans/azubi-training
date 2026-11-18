"""Input validation for JSON requests — one error message per field, in German.

Invalid values are REJECTED (HTTP 400 via the error handler in
`app/__init__.py`), not silently clamped to a valid value.
"""
import re
from datetime import date


class ValidationError(ValueError):
    status = 400

    def __init__(self, message, field=None, details=None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.details = details      # optional, e.g. the colliding sessions


class Conflict(ValidationError):
    """The value is valid but collides with existing data (HTTP 409)."""
    status = 409


class NotFound(ValidationError):
    status = 404


class Forbidden(ValidationError):
    """Permission present, but not for THIS record (e.g. someone else's rating)."""
    status = 403


def _de(num):
    """Number in German format (0,5 instead of 0.5)."""
    return f'{num:g}'.replace('.', ',')


def _raw(data, name):
    value = data.get(name)
    return value.strip() if isinstance(value, str) else value


def text(data, name, label, max_len, required=False):
    value = _raw(data, name)
    if value in (None, ''):
        if required:
            raise ValidationError(f'Bitte „{label}“ ausfüllen.', name)
        return None
    value = str(value)
    if len(value) > max_len:
        raise ValidationError(f'„{label}“ darf höchstens {max_len} Zeichen lang sein.', name)
    return value


def flag(data, name, label):
    """Yes/no from JSON (true/false) or multipart ("true"/"false", "1"/"0") — never bool("false")."""
    value = _raw(data, name)
    if value in (True, 'true', '1', 'on'):
        return True
    if value in (False, None, '', 'false', '0'):
        return False
    raise ValidationError(f'„{label}“ muss Ja oder Nein sein.', name)


def number(data, name, label, lo, hi):
    value = _raw(data, name)
    if value in (None, ''):
        return None
    try:
        num = float(str(value).replace(',', '.'))
    except ValueError:
        raise ValidationError(f'Bitte für „{label}“ eine Zahl eingeben.', name) from None
    if not lo <= num <= hi:
        raise ValidationError(f'Der Wert für „{label}“ muss zwischen {_de(lo)} und {_de(hi)} liegen.', name)
    return num


def integer(data, name, label, lo, hi):
    num = number(data, name, label, lo, hi)
    if num is not None and num != int(num):
        raise ValidationError(f'Bitte für „{label}“ eine ganze Zahl eingeben.', name)
    return None if num is None else int(num)


def iso_date(data, name, label):
    value = _raw(data, name)
    if value in (None, ''):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ValidationError(f'Bitte für „{label}“ ein gültiges Datum eingeben.', name) from None


_LOGIN = re.compile(r'^[a-z0-9._-]{2,120}$')


def login(data, name, label, required=False):
    value = text(data, name, label, 120, required=required)
    if value is None:
        return None
    value = value.lower()
    if not _LOGIN.match(value):
        raise ValidationError(
            f'„{label}“ darf nur Kleinbuchstaben, Ziffern, Punkt, Binde- und Unterstrich enthalten.', name)
    return value


def day(data, name, label, earliest=None, latest=None):
    """Date as a `date` (for Date columns); optionally with bounds."""
    value = iso_date(data, name, label)
    if value is None:
        return None
    result = date.fromisoformat(value)
    if earliest and result < earliest or latest and result > latest:
        raise ValidationError(f'Bitte für „{label}“ ein plausibles Datum eingeben.', name)
    return result


#: Longest selectable period for evaluations (two years).
MAX_PERIOD_DAYS = 731


def optional_period(data, whole):
    """`from`/`to` as (date, date) — both or neither (then (None, None) = `whole`, e.g. "entire course")."""
    first, last = day(data, 'from', 'Von'), day(data, 'to', 'Bis')
    if (first is None) != (last is None):
        raise ValidationError(f'Bitte „Von“ und „Bis“ angeben — oder keins von beiden ({whole}).', 'from')
    if first and first > last:
        raise ValidationError('„Von“ muss vor „Bis“ liegen.', 'from')
    if first and (last - first).days >= MAX_PERIOD_DAYS:
        raise ValidationError('Der Zeitraum darf höchstens zwei Jahre umfassen.', 'from')
    return first, last


_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def email(data, name, label):
    value = text(data, name, label, 200)
    if value is not None and not _EMAIL.match(value):
        raise ValidationError(f'Bitte für „{label}“ eine gültige E-Mail-Adresse eingeben.', name)
    return value


_PHONE = re.compile(r'^\+?[0-9 ()/-]{5,40}$')


def phone(data, name, label):
    value = text(data, name, label, 40)
    if value is not None and not _PHONE.match(value):
        raise ValidationError(f'Bitte für „{label}“ eine gültige Telefonnummer eingeben (Ziffern, +, Leerzeichen).', name)
    return value


_URL = re.compile(r'^https?://[^\s]+$', re.IGNORECASE)


def url(data, name, label):
    """External link — only http(s), so that no javascript:/data: ends up in the href."""
    value = text(data, name, label, 1000)
    if value is not None and not _URL.match(value):
        raise ValidationError('Bitte einen Link beginnend mit http:// oder https:// eingeben.', name)
    return value


def reference(data, name, label, model, current_id=None):
    """ID of a master-data entry. A deactivated entry may remain,
    but may not be newly selected."""
    value = data.get(name)
    if value in (None, ''):
        return None
    try:
        ref_id = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f'Bitte für „{label}“ einen gültigen Eintrag auswählen.', name) from None
    from app.extensions import db
    row = db.session.get(model, ref_id)
    if row is None or (not row.active and ref_id != current_id):
        raise ValidationError(f'Bitte für „{label}“ einen gültigen Eintrag auswählen.', name)
    return row

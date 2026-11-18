"""Bewertungsvorlagen: Eingaben pruefen, Struktur setzen, sperren, kopieren.

Die Struktur (Kategorien, Unterkategorien, Punkte, Gewichte, Grenzen) ist
aenderbar, solange KEINE Bewertung die Vorlage nutzt; danach nur noch Name,
Beschreibung und Niveau. Fuer inhaltliche Aenderungen: `copy()`.
"""
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.assessment import Assessment
from app.models.assessment_category import SKILLS, AssessmentCategory, skill_for_name
from app.models.assessment_criterion import AssessmentCriterion
from app.models.assessment_template import AssessmentTemplate
from app.models.language_level import LanguageLevel
from app.services import validation as v

MAX_CATEGORIES = 20
MAX_CRITERIA = 12
LOCKED = ('Die Vorlage wird bereits für Bewertungen genutzt. Kategorien, Punkte, Gewichte und Grenzen sind '
          'deshalb gesperrt — bitte „Als neue Version kopieren".')


def half_points(data, name, label, lo, hi, required=False):
    """Punktwert in 0,5er-Schritten als Decimal."""
    num = v.number(data, name, label, lo, hi)
    if num is None:
        if required:
            raise v.ValidationError(f'Bitte „{label}“ ausfüllen.', name)
        return None
    if num * 2 != int(num * 2):
        raise v.ValidationError(f'„{label}“: bitte in Schritten von 0,5 Punkten angeben.', name)
    return Decimal(str(num))


def is_used(template):
    return db.session.query(Assessment.id).filter_by(template_id=template.id).first() is not None


def usage_counts(template_ids):
    if not template_ids:
        return {}
    rows = (db.session.query(Assessment.template_id, func.count(Assessment.id))
            .filter(Assessment.template_id.in_(list(template_ids))).group_by(Assessment.template_id))
    return dict(rows)


def _check_name(name, current_id=None):
    q = AssessmentTemplate.query.filter(func.lower(AssessmentTemplate.name) == name.lower(),
                                        AssessmentTemplate.archived_at.is_(None))
    if current_id:
        q = q.filter(AssessmentTemplate.id != current_id)
    if q.first():
        raise v.Conflict('Eine aktive Vorlage mit diesem Namen gibt es bereits.', 'name')


def read_header(data, template=None):
    """Name, Beschreibung, Niveau — immer aenderbar."""
    name = v.text(data, 'name', 'Name', 160, required=template is None or 'name' in data)
    values = {}
    if name is not None:
        _check_name(name, template.id if template else None)
        values['name'] = name
    if template is None or 'description' in data:
        values['description'] = v.text(data, 'description', 'Beschreibung', 4000)
    if template is None or 'level_id' in data:
        level = v.reference(data, 'level_id', 'Niveau', LanguageLevel, template.level_id if template else None)
        values['level_id'] = level.id if level else None
    return values


def _fail(position, name, message):
    label = f'Kategorie {position}' + (f' („{name}“)' if name else '')
    raise v.ValidationError(f'{label}: {message}', 'categories')


def read_structure(data):
    """Bestehensgrenze + Kategorien pruefen. Liefert (passing_percent, [Kategorie-dicts])."""
    passing = v.number(data, 'passing_percent', 'Bestehensgrenze', 0, 100)
    if passing is None:
        raise v.ValidationError('Bitte „Bestehensgrenze“ ausfüllen.', 'passing_percent')
    raw = data.get('categories')
    if not isinstance(raw, list) or not raw:
        raise v.ValidationError('Bitte mindestens eine Kategorie anlegen.', 'categories')
    if len(raw) > MAX_CATEGORIES:
        raise v.ValidationError(f'Höchstens {MAX_CATEGORIES} Kategorien.', 'categories')
    result, names = [], set()
    for position, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise v.ValidationError('Ungültige Kategorie.', 'categories')
        name = item.get('name').strip() if isinstance(item.get('name'), str) else None
        try:
            name = v.text(item, 'name', 'Name', 120, required=True)
            description = v.text(item, 'description', 'Beschreibung', 1000)
            weight = v.number(item, 'weight', 'Gewicht', 0.01, 100)
            if weight is None:
                raise v.ValidationError('Bitte „Gewicht“ ausfüllen (größer als 0).', 'weight')
            criteria = _criteria(item.get('criteria'))
            max_score = half_points(item, 'max_score', 'Höchstpunkte', 0.5, 1000, required=True)
            passing_score = half_points(item, 'passing_score', 'Mindestpunkte', 0, 1000)
            # ohne Angabe: aus dem Namen vorschlagen; ausdruecklich null = keine Fertigkeit
            skill = _skill(item['skill']) if 'skill' in item else skill_for_name(name)
        except v.ValidationError as err:
            _fail(position, name, err.message)
        if name.lower() in names:
            _fail(position, name, 'Der Name kommt doppelt vor.')
        names.add(name.lower())
        if criteria and sum(c['max_score'] for c in criteria) != max_score:
            total = sum(c['max_score'] for c in criteria)
            _fail(position, name, f'Die Höchstpunkte der Unterkategorien ({v._de(float(total))}) müssen die '
                                  f'Höchstpunkte der Kategorie ({v._de(float(max_score))}) ergeben.')
        if passing_score is not None and passing_score > max_score:
            _fail(position, name, 'Die Mindestpunkte dürfen die Höchstpunkte nicht übersteigen.')
        result.append({'name': name, 'description': description, 'weight': Decimal(str(weight)),
                       'max_score': max_score, 'passing_score': passing_score, 'skill': skill,
                       'criteria': criteria})
    return Decimal(str(passing)), result


def _skill(value):
    if value in (None, ''):
        return None
    if value not in SKILLS:
        raise v.ValidationError('Bitte eine gültige Fertigkeit wählen.', 'skill')
    return value


def read_skills(template, raw):
    """{category_id: skill|null} — auch bei gesperrten Vorlagen erlaubt (aendert keine Ergebnisse).

    Liefert {Kategoriename: [alt, neu]} fuer das Protokoll."""
    if not isinstance(raw, dict):
        raise v.ValidationError('Ungültige Zuordnung der Fertigkeiten.', 'skills')
    by_id = {str(c.id): c for c in template.categories}
    changes = {}
    for key, value in raw.items():
        category = by_id.get(str(key))
        if category is None:
            raise v.ValidationError('Die Kategorie gehört nicht zu dieser Vorlage.', 'skills')
        try:
            skill = _skill(value)
        except v.ValidationError as err:
            raise v.ValidationError(err.message, 'skills') from None
        if skill != category.skill:
            changes[category.name] = [SKILLS.get(category.skill), SKILLS.get(skill)]
            category.skill = skill
    return changes


def _criteria(raw):
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_CRITERIA:
        raise v.ValidationError(f'Höchstens {MAX_CRITERIA} Unterkategorien je Kategorie.', 'criteria')
    result, names = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise v.ValidationError('Ungültige Unterkategorie.', 'criteria')
        name = v.text(item, 'name', 'Name der Unterkategorie', 120, required=True)
        if name.lower() in names:
            raise v.ValidationError(f'Die Unterkategorie „{name}“ kommt doppelt vor.', 'criteria')
        names.add(name.lower())
        result.append({'name': name, 'max_score': half_points(item, 'max_score', f'Höchstpunkte „{name}“',
                                                              0.5, 1000, required=True)})
    return result


def set_structure(template, passing_percent, categories):
    """Kategorien komplett ersetzen (nur fuer ungenutzte Vorlagen)."""
    template.passing_percent = passing_percent
    template.categories = [
        AssessmentCategory(name=c['name'], description=c['description'], max_score=c['max_score'],
                           weight=c['weight'], passing_score=c['passing_score'], skill=c['skill'], position=i,
                           criteria=[AssessmentCriterion(name=cr['name'], max_score=cr['max_score'], position=j)
                                     for j, cr in enumerate(c['criteria'])])
        for i, c in enumerate(categories)]


def structure_of(template):
    """Struktur als Eingabe-dict (fuer Kopie und Protokoll-Vergleich)."""
    return {'passing_percent': float(template.passing_percent),
            'categories': [{'name': c.name, 'description': c.description, 'max_score': float(c.max_score),
                            'weight': float(c.weight),
                            'passing_score': None if c.passing_score is None else float(c.passing_score),
                            'skill': c.skill,
                            'criteria': [{'name': cr.name, 'max_score': float(cr.max_score)} for cr in c.criteria]}
                           for c in template.categories]}


def copy_name(name):
    """„B1 Monatsbewertung" -> „B1 Monatsbewertung (Kopie)", bei Bedarf mit Zahl."""
    base, n = f'{name} (Kopie)', 2
    candidate = base
    while AssessmentTemplate.query.filter(func.lower(AssessmentTemplate.name) == candidate.lower(),
                                          AssessmentTemplate.archived_at.is_(None)).first():
        candidate, n = f'{name} (Kopie {n})', n + 1
    return candidate[:160]


def check_usable(template):
    if template is None:
        raise v.ValidationError('Bitte eine Vorlage auswählen.', 'template_id')
    if template.is_archived:
        raise v.ValidationError('Die Vorlage ist archiviert.', 'template_id')

"""Abteilungen (Teams) und ihre Leiter pflegen — Querpruefungen fuer Name und Leiter-Logins."""
from sqlalchemy import func

from app.models.department import Department
from app.models.department_leader import DepartmentLeader
from app.services import access, validation as v

#: Hoechstens so viele Leiter je Abteilung (Schutz gegen Fehleingaben).
MAX_LEADERS = 10


def read(data, department=None):
    """Mitgeschickte Felder pruefen: name, active, leaders (Liste von Logins)."""
    has = (lambda key: key in data) if department else (lambda key: True)
    values = {}
    if has('name'):
        name = v.text(data, 'name', 'Bezeichnung', 80, required=True)
        other = Department.query.filter(func.lower(Department.name) == name.lower(),
                                        Department.id != getattr(department, 'id', None)).first()
        if other is not None:
            raise v.Conflict('Diese Abteilung gibt es bereits.', 'name')
        values['name'] = name
    if 'active' in data:
        values['active'] = v.flag(data, 'active', 'Aktiv')
    if 'leaders' in data:
        values['leaders'] = read_leaders(data.get('leaders'))
    return values


def read_leaders(raw):
    if not isinstance(raw, list) or len(raw) > MAX_LEADERS:
        raise v.ValidationError(f'Bitte bis zu {MAX_LEADERS} Leiter-Logins angeben.', 'leaders')
    logins = []
    for item in raw:
        login = v.login({'leaders': item}, 'leaders', 'Leiter (Login)', required=True)
        if access.trainee_for_login(login) is not None:
            raise v.Conflict(f'„{login}" ist der Login eines Kandidaten und kann nicht Leiter sein.', 'leaders')
        if login not in logins:
            logins.append(login)
    return sorted(logins)


def apply(department, values, actor):
    """Werte uebernehmen; liefert (vorher, nachher) fuer den Verlauf."""
    before = department.to_dict()
    for key in ('name', 'active'):
        if key in values:
            setattr(department, key, values[key])
    if 'leaders' in values:
        current = {x.username: x for x in department.leaders}
        for login in set(current) - set(values['leaders']):
            department.leaders.remove(current[login])
        for login in values['leaders']:
            if login not in current:
                department.leaders.append(DepartmentLeader(username=login, created_by=actor))
    return before

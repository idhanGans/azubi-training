#!/usr/bin/env python3
"""
Naechtlicher E2E-Test fuer azubi-training.

Vertrag + Architektur: infrastructure/nightly-tests.md (main-Repo).
Aufruf:  python test/test.py nightly <produktion|release>

Nur lesend, in beiden Umgebungen gleich — der Test legt nichts an und schickt nichts (die App versendet
keine E-Mails). Er laeuft mit dem Login des Nightly-Nutzers, der in der App eine Rolle haben kann oder
nicht; jeder Fall prueft deshalb gegen die Rechte, die `/api/me` fuer genau diesen Login meldet:
ohne Recht muss die App sperren (403), mit Recht Daten liefern — beides ist gruen, ein 500 nie.
"""
import sys

from _nightly import (
    parse_args,
    resolve_base_url,
    browser,
    NightlyTest,
)

SERVICE = "azubi-training"

# Team-Daten und das Recht, das sie freigibt — ohne Recht erwartet der Test 403.
GUARDED = [
    ("/api/candidates", "candidate.view"),
    ("/api/dashboard", "candidate.view"),
    ("/api/activity", "audit.view"),
]


def _json(page, base_url, path):
    resp = page.request.get(base_url + path)
    assert resp.status < 500, "{} -> HTTP {}".format(path, resp.status)
    ctype = resp.headers.get("content-type", "")
    assert "application/json" in ctype, "{} -> kein JSON ({}), Login-Seite?".format(path, ctype)
    return resp.status, resp.json()


def main():
    args = parse_args(SERVICE)
    env = args.env
    base_url = resolve_base_url(SERVICE, env, args.url)
    nt = NightlyTest(SERVICE, env=env, run=args.run)
    me = {}

    with browser(base_url) as page:
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        with nt.case("Health: App und Datenbank erreichbar"):
            status, body = _json(page, base_url, "/health")
            assert status == 200 and body.get("status") == "ok", body
            assert body.get("database") == "ok", body

        with nt.case("Anmeldung greift: /api/me nennt den Login"):
            status, me = _json(page, base_url, "/api/me")
            assert status == 200, "HTTP {}".format(status)
            assert me.get("user"), me
            assert isinstance(me.get("permissions"), list), me

        with nt.case("Startseite: Oberflaeche oder 'Kein Zugriff', nie Fehler"):
            resp = page.goto(base_url + "/", wait_until="networkidle")
            assert resp is not None and resp.status in (200, 403), \
                "HTTP {}".format(resp.status if resp else "kein Response")
            assert "/login" not in page.url, "Auf Login umgeleitet — Auth fehlt"
            assert page.locator("#sidebar").count() == 1, "App-Huelle (Seitenleiste) fehlt"
            if resp.status == 403:
                assert page.locator(".state [data-i18n='noaccess_title']").is_visible(), "403 ohne Kein-Zugriff-Seite"
                assert not me.get("roles"), "Login hat Rollen, bekommt aber 'Kein Zugriff'"
            else:
                assert page.locator(".topbar h1").is_visible(), "Seite ohne Ueberschrift"
            assert page.locator("html[translate='no']").count() == 1, "Browser-Uebersetzung nicht abgeschaltet"
            assert not errors, "JavaScript-Fehler: {}".format(errors)

        with nt.case("Rechte: Team-Daten nur mit Berechtigung"):
            granted = set(me.get("permissions") or [])
            for path, permission in GUARDED:
                status, body = _json(page, base_url, path)
                expected = 200 if permission in granted else 403
                assert status == expected, "{} -> {} (erwartet {}, Recht {} {})".format(
                    path, status, expected, permission, "da" if permission in granted else "fehlt")
                if status == 403:
                    assert set(body) <= {"error", "code", "field"}, "403 mit Daten: {}".format(sorted(body))

        with nt.case("Kandidatenliste: Daten vollstaendig (nur mit Recht)"):
            if "candidate.view" in set(me.get("permissions") or []):
                status, body = _json(page, base_url, "/api/candidates?per_page=5")
                assert status == 200 and body.get("total", 0) > 0, "keine Kandidaten: {}".format(body.get("total"))
                assert all(c.get("candidate_no") and c.get("name") for c in body["items"]), "Kandidat ohne Nr./Name"

        with nt.case("API-Dokumentation /docs vollstaendig"):
            status, body = _json(page, base_url, "/docs")
            paths = {e.get("path") for e in body.get("endpoints", [])}
            for path in ("/api/me", "/api/candidates", "/api/training/me", "/api/assessments"):
                assert path in paths, "{} fehlt in /docs".format(path)

        with nt.case("CSS, JS und Symbole werden ausgeliefert"):
            for path in ("/static/css/app.css", "/static/js/core.js", "/static/js/i18n.js", "/static/icons.svg"):
                resp = page.request.get(base_url + path)
                assert resp.status == 200, "{} -> HTTP {}".format(path, resp.status)

    return nt.finish()


if __name__ == "__main__":
    sys.exit(main())

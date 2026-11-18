"""`/docs` against reality — the test case EVERY service needs.

`.claude/rules/coding-standards.md` (section "Health + Docs") requires exactly
these two calls as one test case each, per service. They come from
`msh_base.health` (repo `msh/base`) and need at least **msh-base 1.9.0**
— `check_endpoints_documented` arrived with 1.8.0, `check_endpoint_fields` with 1.9.0.
If they are missing on import, the test is not wrong, but the vendored
`msh-base/` copy is too old: pull it from `msh/base@main` (see `msh-base/CLAUDE.md`,
section "Einbindung: VENDORN, nicht klonen").

Build NONE of this yourself. Exactly that happened repeatedly (#14232): three
agents thought the two functions were made up, because their vendored copy
didn't have them, and wrote their own checks — different ones, each with its own
blind spots. The whole point of the helpers is that there is exactly ONE of them.

Both only compute: no log, no exception, nothing on the request path. What the
service deliberately does not document, it names itself via `ignore=` — the
judgment "complete" thus stays with the service.
"""
from msh_base import check_endpoint_fields, check_endpoints_documented

from app import DOCS_ENDPOINTS, create_app


def test_docs_register_passt_zu_den_routen():
    """Both directions: route without an entry AND entry without a route.

    `/health`, `/docs` and Flask's `static` are always excluded; placeholders
    count without their name (`<id>` == `<int:todo_id>`).
    """
    abweichungen = check_endpoints_documented(create_app(), DOCS_ENDPOINTS)
    assert not abweichungen, '\n'.join(str(a) for a in abweichungen)


def test_docs_eintraege_sind_vollstaendig():
    """Every entry carries `description` + `response_example`, write
    methods additionally `request_example`.

    Needs no app — the list itself is checked. Which fields are required
    is set by the service (`required`, `required_for_write`,
    `write_methods`, `ignore`); what's checked is whether the key is there, not
    whether its value is any good.
    """
    abweichungen = check_endpoint_fields(DOCS_ENDPOINTS)
    assert not abweichungen, '\n'.join(str(a) for a in abweichungen)

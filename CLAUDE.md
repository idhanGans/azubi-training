# azubi-training

Training monitoring and language-course management for the apprentice candidates (Azubi-Kandidaten) of Noxt x Planville:
candidates (Kandidaten), instructors (Dozenten), courses (Kurse), timetable (Stundenplan), attendance (Anwesenheit),
assessment engine, module rating (Modul-Bewertung) following the instructors' guideline, progress, candidate portal,
dashboard, reports (Berichte), notifications, curriculum with material, daily reports (Tages-Reports), rating by
SPV/leader (Leiter)/internal team, overall rating (Gesamtbewertung: ranking, Excel/PDF), departments, users/roles,
activity log (Verlauf).
UI in German, EN/ID as a switcher.

Flask monolith following `~/.msh/example-service/`: app factory, one blueprint per area, business logic without Flask in
`app/services/`, Postgres + Alembic, Jinja pages with per-page vanilla JS (no build step).

Before every deploy check that new API endpoints or changes are documented in /docs.

## Structure

| Path | Purpose |
|---|---|
| `app/__init__.py` | App factory (auth, blueprints, error handlers, auto-migration) |
| `app/auth.py` | Token auth for EVERY request + central access check + CSRF (JSON required) |
| `app/navigation.py` | Sidebar — visible is what the page's access rule allows |
| `app/docs.py` | /docs registry, collects `DOCS` from every blueprint module |
| `app/routes/` | one blueprint per area with its own `DOCS` list (large modules: `*_docs.py` next to them) |
| `app/services/permissions.py` | **the one place**: roles -> permissions |
| `app/services/access.py` | Login -> identity (roles, permissions, trainee) |
| `app/services/candidates.py` | Create/change a candidate incl. cross-checks (end >= start, target >= current level) |
| `app/services/candidate_search.py` | Candidate list: search/filter/sort/pages in SQL |
| `app/services/` | further business logic: audit, validation, training_stats |
| `app/routes/curriculum.py`, `modules.py`, `materials.py` | Programmes/curricula, modules, learning material (docs: `curriculum_docs.py`) |
| `app/routes/instructors.py`, `courses.py`, `teaching.py` | Instructors, courses + participants, „Mein Unterricht" (My teaching) (docs: `staff_docs.py`) |
| `app/services/teaching.py`, `candidate_profile.py`, `activity.py` | Assembly of „Mein Unterricht" (key figures, time windows), candidate profile per permission, reading the activity log (filters, option lists) — routes stay thin |
| `app/services/supervision.py` | **the ONE place**: whom a login sees and rates as SPV/leader/internal team |
| `app/services/rating_board.py` | Rating (Bewerten): overview of the ratable candidates + own ratings; key figures from `training_stats.rating_stats` |
| `app/routes/overall.py`, `app/services/overall.py`, `overall_months.py`, `overall_export.py`, `doc_export.py` | Overall rating: **the ONE calculation place** (`overall.py`; per program month, change + trend: `overall_months.py`), downloads (Excel/PDF) |
| `app/routes/departments.py`, `app/services/departments.py` | Maintain departments + leaders (`user.manage`) |
| `app/services/courses.py` | Course cross-checks: module fits the level, instructor active + teaches it |
| `app/routes/sessions.py`, `app/services/scheduling.py` | Timetable: sessions (Termine) + **time conflicts** (instructor/candidate), planning lock, availability hints |
| `app/routes/attendance.py`, `app/services/attendance.py` | Record/correct attendance; **the ONE place for the attendance rate** |
| `app/routes/assessment_templates.py`, `assessments.py`, `app/services/scoring.py` | Assessment templates (Bewertungsvorlagen) + assessments (docs: `assessment_docs.py`); **the ONE calculation place** for results is `scoring.py` |
| `app/routes/lesson_ratings.py`, `app/services/lesson_ratings.py`, `lesson_scoring.py` | Module rating per session (Panduan Penilaian): recording for the whole group incl. attendance, open sessions, evaluation per group, history per candidate; **the ONE calculation place** for points/level is `lesson_scoring.py`; UI `static/js/lesson_view.js` + `pages/lesson.js`, `pages/lesson_reports.js` |
| `app/routes/progress.py`, `app/services/progress.py` | Progress per candidate — **the ONE place** for skill and module progress; charts: `static/js/charts.js` + `progress_view.js` |
| `app/routes/portal.py`, `app/services/portal.py` | Candidate portal: overview, profile, course, modules + material download (own curriculum only) |
| `app/routes/dashboard.py`, `app/services/dashboard.py` | Team overview: **the ONE place** for key-figure definitions (Ø rating, attendance, modules …) and action items (Handlungsbedarf) per permission |
| `app/routes/report_views.py`, `app/services/reports.py`, `csv_export.py` | Reports with period/filters; uniform tables (`columns`/`rows`) for UI + CSV; calculate only via attendance/scoring/progress |
| `app/routes/notifications.py`, `app/services/notifications.py` | Notifications: events + due reminders (on fetch), without duplicates (`dedupe_key`) |
| `app/services/local_time.py` | Local time of the school (ENV `SCHOOL_TZ`, prod/release: Asia/Jakarta = WIB) <-> UTC — the ONLY place for time zones |
| `app/services/scope.py` | **Scope (Reichweite)**: which candidates/courses someone sees (instructor: own courses only) |
| `app/services/file_store.py` | **only** place with file-system access (volume `UPLOAD_DIR`); swap for `s3-api` only here |
| `app/services/file_types.py` | allowed file types per material kind, checked on extension AND magic bytes (no HTML/SVG) |
| `app/routes/catalogs.py` | Master-data lists (`candidate-status`, `language-level`): never delete, only deactivate |
| `app/models/` | one model per file |
| `app/templates/` | `base.html` (app shell) + `pages/*.html` |
| `app/static/` | `css/app.css`, `js/core.js` (API incl. upload, formats, date arithmetic, dialogs), `js/i18n.js`, `js/*_form.js` (forms per area), `js/pages/*.js` |
| `migrations/` | Alembic |
| `tests/` | pytest against real Postgres |

## Access (RBAC)

- Identity comes from the **verified token** (`msh_base.require_msh_auth`
  in `app/auth.py`), never from `X-Auth-*` headers.
- Every route carries `@auth.require_permission('<permission>')`,
  `@auth.candidate_only` or `@auth.authenticated`. Without a rule it is
  locked; `tests/test_rbac.py` checks this for all routes.
- Roles: `SUPER_ADMIN`, `HR`, `ACADEMIC_MANAGER`, `INSTRUCTOR`, `MANAGEMENT`
  from table `user_role` (user management `/users`) or `SUPER_ADMIN` from
  ENV `SUPER_ADMINS`. `CANDIDATE` is whoever's login is attached to a trainee
  (`trainee.msh_user`) — a login is never both. Archived trainees
  no longer have a role. Every other login without a team role is `EVALUATOR`
  (employee, e.g. SPV/leader): it may ONLY rate + see the overall rating (`rating.view`/`rating.create`,
  start page `/ratings`) — for the candidates assigned to it; `tests/test_rating_board.py::EVALUATOR_ENDPOINTS`
  checks this like for the portal.
  Who gets into the app at all is decided by the ZV flag `view`.
- Scope: without `candidate.view_all` (= instructors) ALL routes with
  candidate, report, assessment or course data return only the own,
  non-archived courses and their participants — filtered via `services/scope.py`,
  foreign records answer with 404. New routes with such data must
  go through it. The instructor record is found by `access.resolve` via
  `instructor.msh_user` (`Identity.instructor_id`, rule `auth.instructor_only`).
- Candidates are archived, never deleted (history stays). The
  candidate no. (`K-00001`) is assigned by the DB sequence `candidate_no_seq`.
- Changes land with old/new in `activity_log` (`audit.diff`). Every writing
  route logs (`tests/test_audit.py` checks this; exceptions there with a reason).
  The activity log is immutable: a DB trigger rejects UPDATE/DELETE (migration 0012);
  read only with `audit.view` (super admin).

## Security

- Login/logout centrally via user-handling (SSO, no passwords in the app);
  „Abmelden" (log out) links `/logout` next to `MSH_LOGIN_URL`.
- `app/security.py`: CSP (own scripts only — do not add inline scripts/`onclick`!),
  X-Frame-Options, nosniff, Referrer-Policy; API responses `Cache-Control: no-store`.
- Writing requests: JSON OBJECT or multipart with `X-Requested-With: fetch`, otherwise 400/415.
- Errors: German, API as JSON, pages as `pages/error.html`; stack traces only to the log.
- `tests/test_security.py`: every route without login 401/302, every writing route with
  broken input never 500, candidate A never B, instructor only own records.
- UI: values ALWAYS into HTML via `App.esc()` (no unchecked innerHTML).

## Files (learning material)

- Volume `/app/uploads` (msh_config `volumes`, local-path on the node): **not**
  included in the DB backup, pins the pod to one node (1 replica).
- Files only via `GET /api/materials/<id>/file` (permission check, `nosniff`;
  PDF/images inline, otherwise download with CSP sandbox). Replaced files
  stay (logged with SHA-256). Size: `MAX_UPLOAD_MB` (default 50).
- Uploads are multipart and need `X-Requested-With: fetch` (CSRF rule).

## Timetable

- Sessions: `starts_at`/`ends_at` as `timestamptz` (UTC); input and output in
  local time (`date`, `start`, `end` in the JSON) — the browser never converts itself.
- Participants of a session = participants of its course. Conflicts (instructor or
  candidate booked at the same time) -> 409 with `details`; cancelled sessions and
  archived courses do not count. Checked on create (series: all or
  nothing), move, instructor change, reactivation and when adding new
  participants. Everything under `scheduling.lock()` (advisory lock per transaction).
- Cancel instead of delete (`status=CANCELLED` + reason). Candidates see only
  `public_dict()` (without internal notes).

## Attendance

- One entry per session + candidate (UNIQUE in the DB); a correction overwrites
  with old/new in the activity log. Recording from 15 min before start, never for cancelled
  sessions; recording sets the session to COMPLETED.
- Rate = (present + late) / (present + late + absent);
  excused drops out, only recorded entries of non-cancelled sessions
  count, without entries `None`. For instructors only via their courses.
- Notes are internal: `/api/my-attendance` does not return them.

## Assessments

- Template -> categories (max points, weight, min points) -> optional
  subcategories (sum = max points of the category). Points in 0.5 steps.
- Total = weighted mean of the category percentages (1 decimal);
  passed = total >= the template's threshold AND every category >= min points.
  Calculated ONLY in `services/scoring.py` — including the live preview in the
  browser (`POST /api/assessment-templates/<id>/evaluate`).
- Used templates: structure locked (409), change via „Als neue Version kopieren" (copy as new version).
- DRAFT (internal, incomplete allowed) -> FINAL (complete, result
  stored, visible to the candidate). Corrections only by the examiner or
  academic management (Studienleitung), only with a reason (`reason`, otherwise 400), with old/new in the activity log; drafts can be discarded,
  FINAL never deletable. Examiner and course are fixed after finalising.
- Never changed silently: triggers (migration 0015) reject every change to result, status and points of
  finalised assessments and to the structure of used templates (skill stays free).
  Only finalising and correction call `assessments.allow_result_change()` (`SET LOCAL`) and
  log. Whoever MUST repair data by script sets `azubi.assessment_correction` themselves —
  and writes an activity-log entry.
- History per assessment (`history` in `GET /api/assessments/<id>`, card „Änderungsverlauf"): creation,
  finalising, corrections with who/when/old -> new/reason — for everyone allowed to see the assessment.
- `internal_note` is never in `public_dict()` / `/api/my-assessments`.

## Module rating (Panduan Penilaian Deutschkurs)

- Sheet (Blatt) = session + module + unit (often 2–3 modules per session): per sheet and PRESENT participant one `lesson_rating`
  (`?module_id=&unit=`, modules of the curriculum; without it the module of the session/course). Stars V R W F P 1–3, Pü 0–1,
  Mi 0–2, HA 0–2 (empty = no homework, counts 2), strength/goal (Stärke/Ziel) = list of codes V R W F P L, internal note.
- Empty fields are intended and ignored: aspect averages only over filled values; points/level
  (`complete`) only with all stars + Pü + Mi, otherwise without total and not in the German part. HA required if there
  was homework. Total 5–20, A 18–20 / B 15–17 / C 12–14 / D 5–11, A/B only without a 1-star aspect — only in
  `lesson_scoring.py` (never stored; the UI reads `rules`, preview `POST /api/lesson-ratings/evaluate`).
- `PUT /api/sessions/<id>/lesson-ratings` stores the WHOLE group of a sheet in one transaction, attendance
  via `services/attendance.py` for the whole session. Whoever is later marked absent loses the stars of all sheets of the
  session (`drop_unattended`, in the activity log).
- Open = module sessions of the last 14 days without stars for those present („Mein Unterricht", dashboard); level D of the
  newest rating = action item „Begleitung" (support), level A = extra tasks (evaluation `/lesson-reports`).
- Candidates see their stars, points, level, strength and goal (`/api/my-lesson-ratings`, „Meine Bewertungen"),
  never the note. `mask.sql` empties the notes.

## Progress

- Every category optionally carries a skill (Fertigkeit, `assessment_category.skill`,
  fixed list `SKILLS`); changeable even on locked templates (PATCH `skills`),
  because it changes no result. Without one, the name suggests it.
- Skill per assessment = sum of points / sum of max points of its categories
  (points from `scoring.evaluate`); "current" = newest finalised assessment.
- Modules: completed = before the current course module (course COMPLETED: incl. the current one).
- Charts: one colour, tooltip via mouse/keyboard, every chart with a table view.

## Candidate portal

- Candidates reach ONLY the endpoints in `tests/test_portal.py::CANDIDATE_ENDPOINTS`;
  the test calls every other route with every method and expects 403. A
  new candidate route must be entered there deliberately.
- The start page answers "where am I / what today / when is the next lesson / how good / what to improve /
  how far": `today` (own sessions today + daily report open/submitted, `portal.today_tasks`; if the
  report is missing, the form sits directly in the card — `static/js/report_form.js`, the same as on „Mein Trainings-Report"),
  next sessions, key figures, newest feedback, current module, skills.
- Candidate responses use `public_dict()` (Trainee, Session, Assessment,
  Material): no internal notes, no team logins, no other candidates
  (also no participant list in the course). Material only via
  `/api/my-materials/<id>/file` and only from the curriculum of own courses. Material with `team_only`
  (teacher versions, solutions, model answers) never — neither in the list nor as a file (`portal.py`).

## Rating by SPV, leaders and internal team

- Assignment only in `supervision.py`: SPV = `trainee.supervisor`, leader = `department_leader` of the department
  `trainee.department_id` (free text `trainee.abteilung` = position), internal team = `rating.internal` (all active).
  Deliberately NOT via `scope.py`. Kind (SPV/LEITER/INTERN) is recorded on submission (`staff_rating`, 3 categories
  1–10, one per rater and program month, `rating_board.MONTH_STARTS`; parts average the months). `leiter_rating` unused.
- Others' individual ratings/notes only for the team (`GET /api/ratings`, `assessment.view`), otherwise count/average;
  candidates never see them. Correcting: only your own, only on the day of submission, old/new in the activity log.

## Overall rating

- Rule (weights/shares/working days): constants + docstring only in `overall.py`. Missing part = „Ausstehend" (pending)
  (never 0); total + rank from the parts present, open only without any part. Without `report.view` only
  assigned candidates, only department rank.
- Monatsvergleich (`overall_months.py`, `/overall/months`, `report.view`): parts per program month; change only over
  parts present in BOTH months, trend band `TREND_BAND`.
- Downloads `?format=xlsx|pdf` (`overall_export` -> `doc_export`); PDF: `fonts-dejavu-core`.
- Review notes (`review_notes.py`/`trainee_note`): note per apprentice on 2-week cut-off dates, only `note.edit`; `PUT /api/overall/notes`.

## Reports

- `report.view` (HR, academic management, executive management, admin). Period `from`/`to`,
  default 90 days, max. 2 years; candidate report without `from` = whole history.
- CSV: semicolon, UTF-8 with BOM, decimal comma, text cells starting with `= + - @` are
  defused with `'` (CSV injection). Every export is in the activity log (`report.export`).
- Candidate report without internal notes (may go to the candidate).

## Notifications

- Recipient = login (`trainee.msh_user`/`instructor.msh_user`); without a login no message.
- Events in the same commit as the change (session cancelled/moved,
  course enrolment, assessment published/corrected). Reminders (session
  tomorrow, draft > 3 days, attendance open) are created in `generate_due` on
  fetch — there is no scheduler. UNIQUE (recipient, dedupe_key) against duplicates;
  done items are marked read via `resolve`.
- Text is built in the UI from `nt_<TYPE>` + `params` (DE/EN/ID).

## Conventions

- Date/time: DB `timestamptz` (UTC), display via `App.fmtDate`/`fmtDateTime`/`fmtSlot`
  (`25.09.2026`, `25.09.2026, 10:00 Uhr`, `25.09.2026, 10:00–12:00 Uhr`), ranges `25.09.2026 – 30.09.2026`.
  Session times come from the API as local time. Points in time and `App.todayIso()` calculate in the
  school's time zone (`<html data-tz>` from `local_time.TZ_NAME`), never in the device's.
  Server: "today" only via `local_time.today()`, day/week boundaries in SQL via `timezone(TZ_NAME, …)`.
- New UI texts: German in the template, key in `static/js/i18n.js` (module rating: `i18n_lesson.js`)
  with `de`/`en`/`id`. Formal „Sie" form. `tests/test_i18n.py` checks: every used key
  exists (otherwise it shows raw in the UI), unique, in all three languages.
- Terms: „Kandidat" for the person, „Teilnehmer" (participant) only as member of a course;
  „Report" = daily self-report, „Bericht" = evaluation under /reports.
- No codes in the UI/CSV (RUNNING, CANCELLED …): label via i18n
  (`cs_`/`ss_`/`is_`/`status_`) or, in reports, ready-made German from the server.
- Icons only from `static/icons.svg` (browser `App.icon(name)`, templates macro `icon` from `_icons.html`), no emojis
  (`tests/test_i18n.py` checks this). Buttons as a verb without „+" („Kurs anlegen"); status/badges/single words capitalised
  („Aktiv", „Abgeschlossen", „Ja"); „Angelegt am … von …" via `App.stamp` (without a login only the date).
- Validate forms with `App.validate(form)` instead of `reportValidity()` — the browser messages
  would otherwise come in the browser's language.
- States of every page via `core.js`: `loadingHtml()` at once, `emptyHtml(text)` instead of a gap,
  `showError(host, err, retry)` with „Erneut versuchen" (retry), `toast()` after saving — if
  saving leads to another page, `App.goWithToast(url, text)`. No network = `err_network`, never „Speichern".
- Rule numbers (deadlines, thresholds, defaults) as a named constant in the server — the UI
  never recalculates them but reads them from the API (e.g. `attendance_from`, `windows`,
  `below_percent`, `default_passing_percent`); texts get them as placeholders (`{n}`).
- German date in the server only via `local_time.de_day` (activity log, hints, CSV).
- Routes: check parameters, permission/scope, call the service, respond. Queries with business logic,
  key figures and assemblies belong in `app/services/` (sums once, e.g. `training_stats.report_summary`,
  `scheduling.hours`, `curriculum.curriculum_summary`); the browser does not recalculate sums.
- Input is validated by `app/services/validation.py` (400/404/409 with `field`).
- Responsive: team pages desktop-first, candidate portal for the phone (from 360 px). The page never
  scrolls horizontally — wide tables always in `.tbl-wrap`. Tap targets on touch devices are set
  centrally by `app.css` (`@media (pointer: coarse)`), phone breakpoints `@media (max-width: 600px)`.
- New master-data seed values belong in a migration; `tests/conftest.py`
  reads them from there (`_SEEDS`) and restores them after every test.

## Data integrity

- Who/when: `created_by`/`updated_by` are set centrally by `auth._stamp_actor` before every flush (logged-in
  login), `updated_at` by the model via `onupdate`. Routes need not do it themselves; `audit.diff` skips
  these fields (no change in content). `tests/test_integrity.py` checks across all tables:
  `updated_at` set <=> `updated_by` set.
- Value ranges and statuses are additionally a CHECK in the DB (in the migration, not in the model),
  uniqueness a UNIQUE index. The application checks itself first (message with `field`); if a DB rule
  still fires (concurrent creation), `errors.py` answers 409/400 with `code: DB_RULE`, never 500.
- One request = one transaction (one `commit` at the end, error = rollback). Deleting exists only for
  assessment drafts, course enrolments and roles — everything else is archived/cancelled.

## Performance

- Lists paginated (`page`/`per_page`, or `before_id` in the activity log), never whole tables; sessions only
  with a period, modules only per curriculum.
- Overviews and reports issue a FIXED number of queries — no query per candidate/course/instructor in
  a loop. For that there are batch variants of the same rule (`progress.modules_of`,
  `progress.curriculum_modules`, `AssessmentScore.points_of`, `attendance.stats_by`, grouped counts);
  where only numbers are needed, switch eager loads off with `lazyload`.
  `tests/test_performance.py` checks this (register a new overview there in `PAGES`).
- Load data for measuring: 800 candidates, 8,320 assessments, 80,760 attendances, 6,000 sessions,
  1,000 modules — overview 0.2 s, reports ≤ 0.9 s (2 years), other APIs ≤ 0.15 s.
- CSS/JS with `?v=<commit>` stay in the browser cache for a year (`security.py`); API responses never (`no-store`).

## Masked copy for sandboxes

- `msh_config.json` → `snapshot` (shared-data Postgres) + `mask.sql` in the repo root: `msh snapshot-refresh` builds a
  masked copy of the production DB, `msh snapshot-seed` loads it into user/release, the app migrates on start.
- `mask.sql` runs on EVERY schema state (main 0002 … head): names/contact/login of candidates, instructor names,
  leader notes, names + candidate logins in the activity log (also \u escapes in the JSON), notifications. Reports stay.
  `tests/test_mask.py` checks both states. New personal-data column = line in `mask.sql` + test.
- The pipeline reads `mask.sql` from the PRODUCTION pod — `snapshot-refresh` works only once main runs a version
  with `mask.sql`.

## Migrations

- Schema only via Alembic migration (`migrations/versions/00NN_*.py`), automatically on start
  (`app/startup.py`, advisory lock). Every change in model AND migration — indexes too
  (`__table_args__`), otherwise a later `flask db migrate` deletes them.
- Upgrade never destructive (only add, backfill data deterministically); downgrade complete.
- `tests/test_migrations.py`: every step up and down, models == schema (autogenerate comparison),
  existing data from the current `main` state up to head (adjust the revision there when main catches up).
- Downgrade removes the data of the newer areas — on prod only with a backup first.

## Tests

Real Postgres, locally in the pod via `cp-pg up azubi_test` (port in `_scratch/pg/port`, data survives):

```bash
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:$(cat _scratch/pg/port)/azubi_test cp-pydeps -- python3 -m pytest -q
```

Another DB via `TEST_DATABASE_URL` (name must end in `_test`). Only the auth
counterpart is replaced: in the test the bearer token is the login name.

## Nightly tests

`test/test.py` (contract: `infrastructure/nightly-tests.md` in the main repo, the runner injects the harness `_nightly.py`) —
call `python test/test.py nightly <produktion|release>`, state/runs via `msh nightly`.
Read-only, identical in both environments (creates nothing, the app sends no e-mails): health + DB,
`/api/me`, start page (app shell or „Kein Zugriff", no JS errors), team data exactly per the permissions
of the nightly login (without permission 403 without data, with permission 200), candidate list, `/docs`, CSS/JS/icons.
Locally: put the harness into `_scratch/nightly/`, set `MSH_JWT`, `PYTHONPATH=_scratch/nightly`
(dev server: `--url http://127.0.0.1:5055`, token = login name; the copy must then set the cookie on the URL).

## Lifecycle

Everything via `msh`: `msh deploy` / `msh status` / `msh logs` / `msh shell`.

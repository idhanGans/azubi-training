# Findings

## 2026-09-25 — Creating an instructor without a name gave 500 instead of 400

- **Symptom:** `POST /api/instructors` with `{}` (without `name`) answered with 500
  (`NotNullViolation` on `instructor.name`) instead of a field message.
  Found by the input test in `tests/test_security.py`.
- **Cause:** The route passed the NEW, still empty `Instructor` object to
  `services.instructors.read(data, instructor)`. `read` treats "with object"
  as a partial change and checks only the fields sent — the missing required name
  was never checked and landed as NULL in the database.
- **Fix:** For new objects (without an ID) `_apply` passes `None`, so that on create
  all required fields are checked (`app/routes/instructors.py`).
- **Lesson:** Distinguish "new" and "change" in the call, do not read it off the object,
  which already exists on create. The generic test (every writing route with
  broken input must never return 500) now catches such cases automatically.

## 2026-09-25 — UI text silently overwritten (duplicate i18n key)

- **Symptom:** A new text `rp_empty` for reports would have replaced the existing text
  „Dieser Teilnehmer hat noch keinen Report abgegeben" in the profile.
- **Cause:** A JS object literal with two identical keys silently keeps the last one.
- **Fix:** New key `rpt_empty`; since then `tests/test_i18n.py` checks that every
  key occurs exactly once and has DE/EN/ID.
- **Lesson:** Secure key uniqueness by test, not by review.

## 2026-09-25 — Dialog title as a raw key („dlg_course_add")

- **Symptom:** The dialogs „Kurs anlegen/bearbeiten" and „Vorlage anlegen/bearbeiten" showed
  `dlg_course_add` and `at_add` as their title. Found during the language audit (phase 15) by browser crawl.
- **Cause:** `App.t()` silently falls back to the key for an unknown key. The
  keys `dlg_course_*` were never created, `at_add/at_edit` were called `tpl_add/tpl_edit` in i18n.js.
- **Fix:** Keys added or corrected; `tests/test_i18n.py::test_jeder_benutzte_schluessel_existiert`
  collects every literally used key (t('…'), data-i18n, page titles, navigation) and checks it.
- **Lesson:** A silent fallback needs a test that covers the case it hides.

## 2026-09-25 — Concurrently recorded attendance gave 500

- **Symptom:** If two people (or a double tap) saved the attendance of the same session at the
  same instant, one request answered with 500. Found with `tests/test_concurrency.py`
  (two threads against the real Postgres): `[500, 200]`.
- **Cause:** `attendance.record` reads the existing entries and creates missing ones
  (select-then-insert) — without a lock both see "no entry" and insert; the UNIQUE rule
  (session + candidate) raises `IntegrityError` on the second. The data stayed correct, the response did not.
- **Fix:** `attendance.lock(session)` locks the session row (`SELECT … FOR UPDATE`, without joins —
  `refresh(with_for_update=True)` produces an outer join because of the eager loads, which Postgres rejects)
  and reloads the session afterwards. The second recording waits and then corrects the entry.
- **Lesson:** UNIQUE protects the data, not the response. Every select-then-insert needs a lock
  (like `scheduling.lock()`), and concurrency belongs in the suite as a real thread test.

## 2026-09-25 — Team overview took 7.5 s with 800 candidates (N+1)

- **Symptom:** With load data (800 candidates, 8,320 assessments, 80,760 attendances, 6,000 sessions)
  `/api/dashboard` loaded in 7.5 s with 2,151 SQL queries, the performance report over 2 years in 2.9 s, the
  instructor report in 1.3 s with 230 queries. With the test data (4 candidates) nothing stood out.
- **Cause:** Loops with one query per candidate/course/instructor: `progress.modules(tid)` per candidate
  (courses + modules reloaded), `_held_sessions` per course, five counts per instructor. On top, eager loads:
  every assessment dragged along candidate, course → module → curriculum → programme (JSON learning goals) and points as
  objects — for 6,400 assessments the time went almost entirely into building the objects.
- **Fix:** Batch variants of the same rules: `progress.modules_of(ids)` (a course is evaluated
  once), `progress.curriculum_modules`, `AssessmentScore.points_of(ids)`, grouped counts;
  newest assessment per candidate via `DISTINCT ON`; `lazyload` where only numbers are needed.
  Result: overview 0.2 s / 14 queries, report 0.9 s, instructors 0.1 s — responses compared before/after,
  values identical. `tests/test_performance.py` measures the queries per page with little and
  with more data and fails as soon as they grow.
- **Lesson:** Small test data hides N+1. Pin the number of queries per overview in a test
  (it must not grow with the data), measure the time once with a realistic amount.

## 2026-09-25 — Changes without "who" and 500 on concurrent creation

- **Symptom:** Finalised assessments, re-sorted modules and materials had `updated_at`,
  but no `updated_by` (in the dev DB 31 assessments, 4 modules, 1 material). If two people created
  the same name at the same instant (programme, course, template, login), the second got a 500.
- **Cause:** `updated_at` is set by the model automatically (`onupdate`), `updated_by` had to be set by every route
  itself — finalising and re-sorting did not. The application checks duplicate names via
  SELECT before the INSERT; between the two lies a time window, then the DB's UNIQUE rule fires
  and nobody caught the `IntegrityError`.
- **Fix:** `auth._stamp_actor` (before_flush) sets `created_by`/`updated_by` centrally for every table;
  `errors.py` turns violated DB rules into 409/400 with rollback. `tests/test_integrity.py` checks the
  who/when pairs across all tables and the 409 path.
- **Lesson:** What belongs to EVERY change belongs in one central place, not in every route —
  and checks in the application do not replace the DB rule, they need a response for the case
  that the DB rule fires anyway.

## 2026-09-26 — Enrolling many candidates in a course gave 500 (activity-log text too long)

- **Symptom:** Enrolling all 24 candidates in a course at once ended with 500
  (`value too long for type character varying(400)`), nothing was saved.
- **Cause:** The activity-log entry `course.participants_add` writes all names into `summary`
  (`String(400)`); 24 real names are ~520 characters. With the test data (2–3 short names) it never showed.
- **Fix:** `audit.log` truncates `summary`/`entity_name` centrally to the column length (with „…"); the complete
  list stays in `detail`. Test in `tests/test_audit.py`.
- **Lesson:** Free text from enumerations has no natural upper bound — enforce limits at the place
  that writes into the bounded column, and test with realistic amounts.

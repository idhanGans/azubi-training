-- Anonymisierung fuer maskierte Kopien der Produktiv-DB (msh snapshot-refresh -> release/user-Sandbox).
--
-- Laeuft NUR auf der temporaeren Kopie (nie auf prod) als plain SQL mit ON_ERROR_STOP. Gilt fuer jeden
-- Schema-Stand ab main (0002) bis head: jede Tabelle/Spalte wird vor dem Aendern auf Existenz geprueft.
--
-- Maskiert: Namen, Spitznamen, E-Mail, Telefon, Geburtsdatum und Login der Kandidaten; Namen/E-Mail
-- der Dozenten; Klartext-Notizen der Leiter-, SPV- und Modul-Bewertungen; Namen und Kandidaten-Logins im Verlauf; Benachrichtigungen.
-- Erhalten bleiben: Tages-Reports (Stunden, Bereich, Station, Gelerntes), Bewertungen, Anwesenheit, Kurse,
-- Curriculum, Abteilungen und Team-Logins (Rollen, SPV, Leiter) — genau das, was in der Sandbox geprueft werden soll.

DO $mask$
DECLARE
    cand record;
BEGIN
    -- 1. Verlauf: echte Kandidaten-Namen in Texten durch „Kandidat <Nr>" ersetzen — VOR dem Maskieren der Namen.
    --    Ab Migration 0012 verhindert ein Trigger UPDATE auf activity_log; in der Kopie kurz aus.
    IF to_regclass('public.activity_log') IS NOT NULL AND to_regclass('public.trainee') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE activity_log DISABLE TRIGGER USER';
        -- Je Kandidat einzeln (ein UPDATE … FROM ersetzt pro Zeile nur EINEN Namen, eine Anwesenheit nennt
        -- aber viele); laengste Namen zuerst, damit „Siti" nicht in „Siti Rahma" ersetzt wird.
        -- In `detail` (JSON aus Python) stehen Nicht-ASCII-Zeichen als \uXXXX — beide Schreibweisen ersetzen.
        FOR cand IN
            SELECT id, name, 'Kandidat ' || lpad(id::text, 3, '0') AS masked,
                   (SELECT string_agg(CASE WHEN ascii(c) < 128 THEN c ELSE '\u' || lpad(to_hex(ascii(c)), 4, '0') END,
                                      '' ORDER BY i)
                      FROM unnest(string_to_array(name, NULL)) WITH ORDINALITY AS x(c, i)) AS escaped
              FROM trainee WHERE length(name) > 2 ORDER BY length(name) DESC
        LOOP
            UPDATE activity_log SET summary = replace(summary, cand.name, cand.masked)
             WHERE strpos(summary, cand.name) > 0;
            UPDATE activity_log SET detail = replace(replace(detail::text, cand.name, cand.masked), cand.escaped, cand.masked)::json
             WHERE detail IS NOT NULL
               AND (strpos(detail::text, cand.name) > 0 OR strpos(detail::text, cand.escaped) > 0);
        END LOOP;
        UPDATE activity_log SET entity_name = 'Kandidat ' || lpad(entity_id::text, 3, '0') WHERE entity_type = 'trainee';
        -- Kandidaten-Logins (oft der echte Name) als Handelnde: „kandidat-<Nr>"
        UPDATE activity_log a SET actor = 'kandidat-' || lpad(t.id::text, 3, '0')
          FROM trainee t WHERE t.msh_user IS NOT NULL AND a.actor = t.msh_user;
        EXECUTE 'ALTER TABLE activity_log ENABLE TRIGGER USER';
    END IF;

    -- 2. Kandidaten
    IF to_regclass('public.trainee') IS NOT NULL THEN
        UPDATE trainee SET name = 'Kandidat ' || lpad(id::text, 3, '0'), nickname = NULL, email = NULL, msh_user = NULL;
        IF EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'trainee' AND column_name = 'phone') THEN
            EXECUTE 'UPDATE trainee SET phone = NULL, date_of_birth = NULL';          -- ab Migration 0004
        END IF;
    END IF;

    -- 3. Dozenten (ab Migration 0006) — Login bleibt, damit Team-Rollen in der Sandbox greifen
    IF to_regclass('public.instructor') IS NOT NULL THEN
        UPDATE instructor SET name = 'Dozent ' || id, email = NULL;
    END IF;

    -- 4. Freitext-Notizen der Leiter-Bewertungen (Einschaetzungen zur Person)
    IF to_regclass('public.leiter_rating') IS NOT NULL THEN
        UPDATE leiter_rating SET note = NULL WHERE note IS NOT NULL;
    END IF;
    -- 4a. Notizen der SPV-/Leiter-/internen Bewertungen (ab Migration 0020) — Punkte bleiben
    IF to_regclass('public.staff_rating') IS NOT NULL THEN
        EXECUTE 'UPDATE staff_rating SET note = NULL WHERE note IS NOT NULL';
    END IF;
    -- 4b. Notizen der Modul-Bewertungen (ab Migration 0019) — Sterne/Level bleiben
    IF to_regclass('public.lesson_rating') IS NOT NULL THEN
        EXECUTE 'UPDATE lesson_rating SET note = NULL WHERE note IS NOT NULL';
    END IF;

    -- 5. Benachrichtigungen enthalten Namen in den Platzhaltern — in der Kopie ohne Nutzen
    IF to_regclass('public.notification') IS NOT NULL THEN
        DELETE FROM notification;
    END IF;
END
$mask$;

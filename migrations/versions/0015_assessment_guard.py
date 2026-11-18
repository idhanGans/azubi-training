"""Abgeschlossene Bewertungen: Ergebnis und Punkte aendern sich nie still

Die Anwendung aendert eine abgeschlossene Bewertung nur ueber die Korrektur (Pruefer oder
Studienleitung, Alt -> Neu + Grund im Verlauf) und sperrt benutzte Vorlagen. Diese Trigger sichern
dasselbe in der Datenbank — auch gegen Skripte, direkte SQL-Aenderungen oder einen Fehler im Code:

- assessment: Status, Ergebnis, Bestanden, Kandidat, Vorlage, Abschluss einer abgeschlossenen
  Bewertung aendern, eine abgeschlossene anlegen oder loeschen -> abgelehnt
- assessment_score: Punkte einer abgeschlossenen Bewertung anlegen/aendern/entfernen -> abgelehnt
- Vorlage mit abgeschlossenen Bewertungen: Bestehensgrenze, Kategorien/Unterkategorien (Hoechstpunkte,
  Gewicht, Mindestpunkte, hinzufuegen, entfernen) -> abgelehnt (die Fertigkeit bleibt aenderbar)

Erlaubt nur, wenn die Transaktion `SET LOCAL azubi.assessment_correction = 'on'` gesetzt hat — das tun
ausschliesslich Abschliessen und Korrektur (`services/assessments.allow_result_change`).

Keine Daten werden veraendert.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-25 18:00:00
"""
from alembic import op

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None

_ALLOWED = "current_setting('azubi.assessment_correction', true) IS NOT DISTINCT FROM 'on'"
_REFUSE = ("RAISE EXCEPTION 'Abgeschlossene Bewertungen aendern sich nur ueber die Korrektur (%)', {what} "
           "USING ERRCODE = 'insufficient_privilege'")

FUNCTIONS = {
    'assessment_final_guard': f"""
        BEGIN
            IF {_ALLOWED} THEN IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.status = 'FINAL' THEN {_REFUSE.format(what="'assessment ' || OLD.id")}; END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status = 'FINAL' THEN {_REFUSE.format(what="'assessment neu'")}; END IF;
                RETURN NEW;
            END IF;
            IF (OLD.status = 'FINAL' OR NEW.status = 'FINAL')
               AND (NEW.status, NEW.overall_percent, NEW.passed, NEW.trainee_id, NEW.template_id,
                    NEW.finalized_at, NEW.finalized_by)
                   IS DISTINCT FROM (OLD.status, OLD.overall_percent, OLD.passed, OLD.trainee_id, OLD.template_id,
                                     OLD.finalized_at, OLD.finalized_by) THEN
                {_REFUSE.format(what="'assessment ' || OLD.id")};
            END IF;
            RETURN NEW;
        END""",
    'assessment_score_guard': f"""
        BEGIN
            IF {_ALLOWED} THEN IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END IF;
            IF EXISTS (SELECT 1 FROM assessment WHERE status = 'FINAL'
                       AND id IN (CASE WHEN TG_OP <> 'INSERT' THEN OLD.assessment_id END,
                                  CASE WHEN TG_OP <> 'DELETE' THEN NEW.assessment_id END)) THEN
                {_REFUSE.format(what="'Punkte'")};
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END""",
    'assessment_structure_guard': f"""
        DECLARE
            tpl integer;
        BEGIN
            IF {_ALLOWED} THEN IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'assessment_template' THEN
                IF NEW.passing_percent IS NOT DISTINCT FROM OLD.passing_percent THEN RETURN NEW; END IF;
                tpl := OLD.id;
            ELSIF TG_TABLE_NAME = 'assessment_category' THEN
                IF TG_OP = 'UPDATE' AND (NEW.template_id, NEW.max_score, NEW.weight, NEW.passing_score)
                   IS NOT DISTINCT FROM (OLD.template_id, OLD.max_score, OLD.weight, OLD.passing_score) THEN
                    RETURN NEW;
                END IF;
                tpl := CASE WHEN TG_OP = 'INSERT' THEN NEW.template_id ELSE OLD.template_id END;
            ELSE
                IF TG_OP = 'UPDATE' AND (NEW.category_id, NEW.max_score)
                   IS NOT DISTINCT FROM (OLD.category_id, OLD.max_score) THEN
                    RETURN NEW;
                END IF;
                SELECT template_id INTO tpl FROM assessment_category
                 WHERE id = CASE WHEN TG_OP = 'INSERT' THEN NEW.category_id ELSE OLD.category_id END;
            END IF;
            IF EXISTS (SELECT 1 FROM assessment WHERE template_id = tpl AND status = 'FINAL') THEN
                {_REFUSE.format(what="'Vorlage ' || tpl")};
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END""",
}
TRIGGERS = [
    ('assessment_final_guard', 'assessment', 'INSERT OR UPDATE OR DELETE', 'assessment_final_guard'),
    ('assessment_score_guard', 'assessment_score', 'INSERT OR UPDATE OR DELETE', 'assessment_score_guard'),
    ('assessment_template_guard', 'assessment_template', 'UPDATE', 'assessment_structure_guard'),
    ('assessment_category_guard', 'assessment_category', 'INSERT OR UPDATE OR DELETE', 'assessment_structure_guard'),
    ('assessment_criterion_guard', 'assessment_criterion', 'INSERT OR UPDATE OR DELETE', 'assessment_structure_guard'),
]


def upgrade():
    for name, body in FUNCTIONS.items():
        op.execute(f'CREATE FUNCTION {name}() RETURNS trigger AS $$ {body} $$ LANGUAGE plpgsql')
    for trigger, table, events, function in TRIGGERS:
        op.execute(f'CREATE TRIGGER {trigger} BEFORE {events} ON {table} FOR EACH ROW EXECUTE FUNCTION {function}()')


def downgrade():
    for trigger, table, _, _ in reversed(TRIGGERS):
        op.execute(f'DROP TRIGGER {trigger} ON {table}')
    for name in reversed(list(FUNCTIONS)):
        op.execute(f'DROP FUNCTION {name}()')

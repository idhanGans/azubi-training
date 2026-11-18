"""Bestand aus dem alten Trainings-Monitoring: Fachrichtung „leer" = keine Fachrichtung

Die alte Oberflaeche fragte „Fach (Elektro / SHK / leer)" per Eingabefeld — eingetragen wurde dabei
woertlich „leer" (auf prod bei allen 24 Kandidaten). Die neue App kennt nur Elektro, SHK oder keine;
„leer" stand sonst als Fachrichtung in Listen und fiel aus der Top-12-Auswahl.

- „leer" (Gross/Klein, Leerzeichen egal) -> NULL
- „elektro"/„shk" in anderer Schreibweise -> „Elektro"/„SHK"

Gleichbedeutend, nichts geht verloren. Downgrade laesst die Werte leer (NULL hiess vorher dasselbe).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-26 05:00:00
"""
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE trainee SET fach = NULL WHERE lower(btrim(fach)) IN ('leer', '')")
    op.execute("UPDATE trainee SET fach = 'Elektro' WHERE lower(btrim(fach)) = 'elektro' AND fach <> 'Elektro'")
    op.execute("UPDATE trainee SET fach = 'SHK' WHERE lower(btrim(fach)) = 'shk' AND fach <> 'SHK'")


def downgrade():
    pass    # Werte bleiben normalisiert — „leer" und NULL bedeuten dasselbe

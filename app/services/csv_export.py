"""CSV fuer Berichte — so, dass deutsches Excel sie direkt oeffnet und keine Formeln ausfuehrt.

- Semikolon als Trenner, UTF-8 mit BOM (Umlaute), Dezimalkomma.
- Text-Zellen, die mit = + - @ (oder Tab/CR) beginnen, bekommen ein fuehrendes ' —
  sonst koennte ein Name wie „=HYPERLINK(…)" in Excel als Formel laufen (CSV-Injection).
"""
import csv
import io

from app.services.local_time import de_day

_DANGEROUS = ('=', '+', '-', '@', '\t', '\r')


def _cell(value, kind):
    if value is None:
        return ''
    if kind == 'rate':
        value = round(value * 100, 1)
    if kind == 'date':
        value = de_day(value)
    if isinstance(value, bool):
        return 'Ja' if value else 'Nein'
    if isinstance(value, float):
        return f'{value:g}'.replace('.', ',')
    if isinstance(value, int):
        return str(value)                     # Zahlen (auch negative) bleiben Zahlen
    if isinstance(value, (list, tuple)):
        value = ', '.join(str(v) for v in value)
    text = str(value)
    return "'" + text if text.startswith(_DANGEROUS) else text


def render(table):
    """`table` = {'columns': [{'key', 'label', 'type'}], 'rows': [dict]} -> CSV-Text (mit BOM)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';', quoting=csv.QUOTE_MINIMAL, lineterminator='\r\n')
    writer.writerow([c['label'] + (' (%)' if c.get('type') == 'rate' else '') for c in table['columns']])
    for row in table['rows']:
        writer.writerow([_cell(row.get(c['key']), c.get('type')) for c in table['columns']])
    return '﻿' + out.getvalue()

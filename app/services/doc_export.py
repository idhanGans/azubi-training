"""Downloads als Excel (.xlsx) und PDF — aus EINER Beschreibung, damit beide Formate dasselbe zeigen.

`doc` = {'title', 'meta': [Zeile], 'landscape': bool, 'sections': [Abschnitt]}; ein Abschnitt hat `title` und
ENTWEDER `pairs` ([(Bezeichnung, Wert)]) ODER `columns` ([{'key', 'label', 'type'}]) + `rows` ([dict]).
Typen: text (Standard), number (1 Nachkommastelle), int, rate (0..1 -> %), date (JJJJ-MM-TT).
Leere Werte stehen als „–". Text, der mit = + - @ beginnt, bleibt in Excel Text (keine Formel).
"""
import io

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.local_time import de_day

#: Schrift mit Umlauten/Sonderzeichen (Debian-Paket fonts-dejavu-core, siehe Dockerfile)
FONT_DIR = '/usr/share/fonts/truetype/dejavu'
EMPTY = '–'
_HEAD_FILL = PatternFill('solid', fgColor='E8EEF4')
_NEXT_LINE = {'new_x': XPos.LMARGIN, 'new_y': YPos.NEXT}
_MAX_WIDTH = 60


def _num(value, digits=1):
    return f'{value:.{digits}f}'.replace('.', ',')


def text_of(value, kind=None):
    """Anzeige-Text einer Zelle (PDF und Paare)."""
    if value is None or value == '':
        return EMPTY
    if kind == 'rate' and isinstance(value, (int, float)):
        return _num(value * 100) + ' %'
    if kind == 'date':
        return de_day(value)
    if isinstance(value, float) or (kind == 'number' and isinstance(value, int) and not isinstance(value, bool)):
        return _num(value)
    if isinstance(value, (list, tuple)):
        return ', '.join(str(v) for v in value) or EMPTY
    return str(value)


# ---------- Excel ----------

def _xlsx_cell(ws, row, col, value, kind=None, bold=False):
    cell = ws.cell(row=row, column=col)
    if value is None or value == '':
        cell.value = EMPTY
    elif kind == 'rate' and isinstance(value, (int, float)):
        cell.value, cell.number_format = value, '0.0%'
    elif kind in ('number', 'int') and isinstance(value, (int, float)):
        cell.value = value
        cell.number_format = '0' if kind == 'int' else '0.0'
    elif kind == 'date':
        cell.value = de_day(value)
    else:
        cell.value = text_of(value)
        cell.data_type = 's'                     # „=…" bleibt Text, keine Formel
    if bold:
        cell.font = Font(bold=True)
    cell.alignment = Alignment(vertical='top', wrap_text=True)
    return cell


def xlsx(doc):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Bericht'
    widths = {}
    row = 1
    ws.cell(row=row, column=1, value=doc['title']).font = Font(bold=True, size=14)
    for line in doc.get('meta', []):
        row += 1
        _xlsx_cell(ws, row, 1, line)
    for section in doc['sections']:
        row += 2
        ws.cell(row=row, column=1, value=section['title']).font = Font(bold=True, size=12)
        if 'pairs' in section:
            for label, value in section['pairs']:
                row += 1
                _xlsx_cell(ws, row, 1, label, bold=True)
                _xlsx_cell(ws, row, 2, value)
                widths[1] = max(widths.get(1, 0), len(str(label)))
                widths[2] = max(widths.get(2, 0), len(text_of(value)))
            continue
        row += 1
        for col, c in enumerate(section['columns'], start=1):
            cell = _xlsx_cell(ws, row, col, c['label'], bold=True)
            cell.fill = _HEAD_FILL
            widths[col] = max(widths.get(col, 0), len(c['label']))
        if not section['rows']:
            row += 1
            _xlsx_cell(ws, row, 1, section.get('empty', EMPTY))
        for item in section['rows']:
            row += 1
            for col, c in enumerate(section['columns'], start=1):
                value = item.get(c['key'])
                _xlsx_cell(ws, row, col, value, c.get('type'))
                widths[col] = max(widths.get(col, 0), len(text_of(value, c.get('type'))))
    for col, width in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = min(max(width + 2, 8), _MAX_WIDTH)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---------- PDF ----------

class _Pdf(FPDF):
    def __init__(self, title, landscape):
        super().__init__(orientation='L' if landscape else 'P', unit='mm', format='A4')
        self.add_font('DejaVu', '', f'{FONT_DIR}/DejaVuSans.ttf')
        self.add_font('DejaVu', 'B', f'{FONT_DIR}/DejaVuSans-Bold.ttf')
        self.doc_title = title
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(12, 12, 12)

    def footer(self):
        self.set_y(-10)
        self.set_font('DejaVu', '', 7)
        self.set_text_color(110)
        self.cell(0, 5, f'{self.doc_title} · Seite {self.page_no()}/{{nb}}', align='R')
        self.set_text_color(0)


def _widths(section, total):
    """Spaltenbreiten (Zeichen -> mm): jede Spalte mindestens so breit wie ihr laengstes Wort (kein Umbruch
    mitten im Wort), der Rest der Seitenbreite nach Inhaltslaenge (gedeckelt) verteilt."""
    need, want = [], []
    for c in section['columns']:
        texts = [c['label']] + [text_of(r.get(c['key']), c.get('type')) for r in section['rows']]
        need.append(max(len(word) for text in texts for word in text.split()) + 1)
        want.append(max(min(max(len(text) for text in texts), 40), need[-1]))
    extra = [w - n for n, w in zip(need, want)]
    char = total / sum(want)
    if sum(need) * char >= total or not sum(extra):
        return [w * char for w in want]
    char = min(char * 1.5, total / sum(need))            # Wort-Breite in mm (Schrift 8 pt) mit Luft
    rest = total - sum(need) * char
    return [n * char + rest * e / sum(extra) for n, e in zip(need, extra)]


def pdf(doc):
    p = _Pdf(doc['title'], doc.get('landscape', False))
    p.add_page()
    width = p.w - p.l_margin - p.r_margin
    p.set_font('DejaVu', 'B', 14)
    p.multi_cell(width, 7, doc['title'], **_NEXT_LINE)
    p.set_font('DejaVu', '', 8)
    for line in doc.get('meta', []):
        p.multi_cell(width, 4.5, line, **_NEXT_LINE)
    head = FontFace(emphasis='BOLD', fill_color=(232, 238, 244))
    for section in doc['sections']:
        p.ln(3)
        p.set_font('DejaVu', 'B', 11)
        p.multi_cell(width, 6, section['title'], **_NEXT_LINE)
        p.set_font('DejaVu', '', 8)
        if 'pairs' in section:
            with p.table(col_widths=(width * 0.35, width * 0.65), first_row_as_headings=False,
                         line_height=4.5, padding=1, text_align='LEFT') as table:
                for label, value in section['pairs']:
                    r = table.row()
                    r.cell(str(label), style=FontFace(emphasis='BOLD'))
                    r.cell(text_of(value))
            continue
        if not section['rows']:
            p.multi_cell(width, 5, section.get('empty', EMPTY), **_NEXT_LINE)
            continue
        with p.table(col_widths=_widths(section, width), headings_style=head, line_height=4.5, padding=1,
                     repeat_headings=1, text_align='LEFT') as table:
            r = table.row()
            for c in section['columns']:
                r.cell(c['label'])
            for item in section['rows']:
                r = table.row()
                for c in section['columns']:
                    r.cell(text_of(item.get(c['key']), c.get('type')))
    return bytes(p.output())

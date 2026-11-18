/* Berichts-Tabellen: eine Darstellung fuer alle Berichte (Spaltentyp aus der API), sortierbar, mit CSV-Link.
   Werte kommen fertig vom Server (app/services/reports.py) — hier wird nur formatiert. */
const ReportTable = (() => {
  const {esc, t, fmtNum, fmtDate} = App;

  function cell(value, type, row) {
    if (value == null || value === '') return '–';
    switch (type) {
      case 'candidate': return `<a href="/candidates/${row.candidate_id}">${esc(value)}</a>`;
      case 'rate': return esc(`${fmtNum(value * 100, 1)} %`);
      case 'percent': return esc(`${fmtNum(value, 1)} %`);
      case 'hours': return esc(`${fmtNum(value, 2)} h`);
      case 'int': return esc(fmtNum(value, 0));
      case 'date': return esc(fmtDate(value));
      case 'bool': return `<span class="badge ${value ? 'ok' : 'warn'}">${esc(t(value ? 'as_passed' : 'as_failed'))}</span>`;
      default: return esc(Array.isArray(value) ? value.join(', ') : value);
    }
  }

  const NUMERIC = ['rate', 'percent', 'hours', 'int'];

  /* Tabelle rendern; csvUrl = Download-Link fuer genau diese Tabelle (oder null). */
  function html(table, csvUrl, sort) {
    const rows = [...table.rows];
    if (sort && sort.table === table.id) {
      const c = table.columns.find(x => x.key === sort.key);
      const num = c && NUMERIC.includes(c.type);
      rows.sort((a, b) => {
        const x = a[sort.key], y = b[sort.key];
        if (x == null) return 1;
        if (y == null) return -1;
        const r = num ? x - y : String(x).localeCompare(String(y), 'de');
        return sort.desc ? -r : r;
      });
    }
    const arrow = key => (sort && sort.table === table.id && sort.key === key ? (sort.desc ? ' ▼' : ' ▲') : '');
    return `<section class="card report-table"><div class="pghead"><h3>${esc(table.title)}</h3>
        <span class="meta">${esc(t('rp_rows', {n: table.rows.length}))}</span>
        ${csvUrl ? `<div class="tools no-print"><a class="btn ghost sm" href="${esc(csvUrl)}" download>${esc(t('rp_csv'))}</a></div>` : ''}</div>
      ${rows.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>${table.columns.map(c => `<th${NUMERIC.includes(c.type) ? ' class="c"' : ''}>
        <button class="sort" type="button" data-sort="${esc(table.id)}|${esc(c.key)}">${esc(c.label)}${arrow(c.key)}</button></th>`).join('')}</tr></thead>
        <tbody>${rows.map(r => `<tr>${table.columns.map(c => `<td${NUMERIC.includes(c.type) ? ' class="c"' : c.type === 'candidate' ? ' class="name"' : ''}>${cell(r[c.key], c.type, r)}</td>`).join('')}</tr>`).join('')}</tbody>
      </table></div>` : App.emptyHtml(t('rpt_empty'))}</section>`;
  }

  return {html, cell};
})();

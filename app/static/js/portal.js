/* Kandidaten-Portal: gemeinsame Bausteine (Termin-Zeile, Kennzahl-Kachel, Fakten-Liste). */
const Portal = (() => {
  const {esc, t, fmtDate, fmtTimeRange} = App;

  /* Termin als Listenzeile; showDate = Datum statt nur Uhrzeit vorn (Uebersicht, Kurs). */
  function sessionHtml(s, {showDate} = {}) {
    const where = [s.room, s.location].filter(Boolean).join(' · ');
    return `<li class="my-sess${s.status === 'CANCELLED' ? ' cancelled' : ''}">
      <span class="sess-time">${showDate ? `${esc(fmtDate(s.date))}<br>` : ''}${esc(fmtTimeRange(s.start, s.end))}</span>
      <div><b>${esc(s.course.name)}</b> ${SessionForm.statusBadge(s)}
        ${s.module ? `<div>${esc(s.module.name)}</div>` : ''}
        <div class="meta">${esc([s.instructor && s.instructor.name, where].filter(Boolean).join(' · '))}</div>
        ${s.cancel_reason ? `<div class="meta">${esc(t('f_cancel_reason'))}: ${esc(s.cancel_reason)}</div>` : ''}
        ${s.online_url && s.status !== 'CANCELLED' ? `<a class="btn ghost sm" href="${esc(s.online_url)}" target="_blank" rel="noopener noreferrer">${esc(t('se_join'))}</a>` : ''}
      </div></li>`;
  }

  /* small: langer Wert (z.B. Datum + Uhrzeit) in kleinerer Schrift, damit die Kachel nicht umbricht. */
  const tile = (value, labelKey, href, small) => `<a class="stat link-stat" href="${esc(href)}"><b${small ? ' class="small"' : ''}>${esc(value)}</b><span>${esc(t(labelKey))}</span></a>`;

  const facts = rows => `<dl class="facts">${rows.map(([label, value]) => `<dt>${esc(t(label))}</dt>
    <dd>${value == null || value === '' ? '–' : esc(value)}</dd>`).join('')}</dl>`;

  return {sessionHtml, tile, facts};
})();

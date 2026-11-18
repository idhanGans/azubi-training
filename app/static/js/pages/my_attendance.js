/* Kandidat: eigene Anwesenheit — Quote, Zaehler, Eintraege (neueste zuerst). */
(() => {
  const {$, esc, t, api, fmtDate, fmtTimeRange} = App;
  const host = $('#page');
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', '/api/my-attendance');
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function render() {
    const s = data.stats;
    if (!s.recorded) {
      host.innerHTML = `<div class="card">${App.emptyHtml(t('at_none_yet_own'))}</div>`;
      return;
    }
    host.innerHTML = `<div class="card hero"><h2>${esc(t('at_rate_line', {r: AttendanceForm.rateText(s.rate)}))}</h2>
        <p>${esc(AttendanceForm.countsText(s))}</p><p class="meta">${esc(t('at_rule'))}</p></div>
      <section class="card"><h3>${esc(t('at_history'))}</h3><ul class="plain">
        ${data.records.map(r => `<li class="my-sess"><span class="sess-time">${esc(fmtDate(r.session.date))}</span>
          <div><b>${esc(r.session.course.name)}</b> <span class="meta">${esc(fmtTimeRange(r.session.start, r.session.end))}</span><br>
          ${AttendanceForm.statusBadge(r.status)}${r.minutes_late ? ` <span class="meta">${esc(t('at_minutes', {n: r.minutes_late}))}</span>` : ''}</div></li>`).join('')}
      </ul></section>`;
  }

  App.onRerender(() => data && render());
  load();
})();

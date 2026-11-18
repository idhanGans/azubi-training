/* Team: Trainings-Monitoring — Teilnehmer, Kennzahlen, Reports, Bewertungen. */
(() => {
  const {$, esc, t, api, fmtDate, fmtDateTime, fmtNum} = App;
  const host = $('#page');
  let trainees = null;

  const byId = id => trainees.find(x => x.id === id);
  const displayName = x => x.nickname || x.name;
  const ratings = x => [x.spv.mean, x.intern.mean].map(v => fmtNum(v)).join(' / ');

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      trainees = (await api('GET', '/api/trainees')).trainees;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function rowHtml(x) {
    const actions = `<button class="btn ghost sm" type="button" data-action="reports" data-id="${x.id}">${esc(t('btn_reports'))}</button>`;
    return `<tr>
      <td class="name"><a href="/candidates/${x.id}">${esc(x.name)}</a>
        ${x.nickname ? `<span class="mut">(${esc(x.nickname)})</span>` : ''}</td>
      <td>${esc(x.fach || '–')}</td><td class="nw">${esc(x.abteilung || '–')}</td>
      <td class="nw">${x.msh_user ? esc(x.msh_user) : `<span class="mut">${esc(t('not_assigned'))}</span>`}</td>
      <td class="c">${esc(fmtNum(x.hours_total))}</td><td class="c">${x.days_reported}</td>
      <td class="c">${x.lang_count} / ${x.tech_count}</td><td class="c nw">${esc(ratings(x))}</td>
      <td class="nw">${esc(fmtDateTime(x.last_report))}</td><td><div class="row-actions">${actions}</div></td></tr>`;
  }

  function render() {
    host.innerHTML = `<div class="card">
      <div class="pghead"><span class="meta">${esc(t('tm_count', {n: trainees.length}))}</span>
        <div class="tools"><a class="btn ghost sm" href="/candidates">${esc(t('nav_candidates'))}</a></div></div>
      <p class="hint">${esc(t('tm_hint'))}</p>
      ${trainees.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>
        <th>${esc(t('f_name'))}</th><th>${esc(t('f_fach'))}</th><th>${esc(t('f_abteilung'))}</th><th>${esc(t('th_login'))}</th>
        <th class="c">${esc(t('th_hours'))}</th><th class="c">${esc(t('th_days'))}</th><th class="c">${esc(t('th_langtech'))}</th>
        <th class="c">${esc(t('th_rating'))}</th><th>${esc(t('th_last'))}</th><th>${esc(t('th_actions'))}</th>
      </tr></thead><tbody>${trainees.map(rowHtml).join('')}</tbody></table></div>` : App.emptyHtml(t('tm_empty'))}
    </div>`;
  }

  async function showReports(id) {
    const x = byId(id);
    const dlg = App.openDialog(t('rp_title', {name: displayName(x)}), App.loadingHtml());
    const body = dlg.querySelector('.dlg-body');
    try {
      const reports = (await api('GET', `/api/training?trainee_id=${id}`)).reports;
      body.innerHTML = reports.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>
        <th>${esc(t('th_date'))}</th><th class="c">${esc(t('th_hours'))}</th><th>${esc(t('th_area'))}</th>
        <th>${esc(t('f_station'))}</th><th>${esc(t('th_learned'))}</th><th>${esc(t('th_entered'))}</th></tr></thead><tbody>
        ${reports.map(r => `<tr><td class="nw">${esc(fmtDate(r.period))}</td><td class="c">${esc(fmtNum(r.hours))}</td>
          <td>${esc([r.lang ? t('f_lang') : '', r.tech ? t('f_tech') : ''].filter(Boolean).join(', ') || '–')}</td>
          <td class="nw">${esc(r.station || '–')}</td><td class="wrap">${esc(r.learned || '–')}</td>
          <td class="nw">${esc(fmtDateTime(r.created_at))}</td></tr>`).join('')}</tbody></table></div>` : App.emptyHtml(t('rp_empty'));
    } catch (err) {
      body.innerHTML = `<div class="state error" role="alert">${esc(err.message)}</div>`;
    }
  }

  App.onActions(host, {
    reports: showReports,
  });
  App.onRerender(() => trainees && render());
  load();
})();

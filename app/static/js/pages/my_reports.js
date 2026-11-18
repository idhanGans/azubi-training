/* Kandidatenportal: eigener Tages-Report + eigene Historie. */
(() => {
  const {$, esc, t, api, fmtDate, fmtDateTime, fmtNum, toast} = App;
  const host = $('#page');
  let state = null;       // {trainee, reports, summary}
  let editId = null;

  const area = r => [r.lang ? t('f_lang') : '', r.tech ? t('f_tech') : ''].filter(Boolean).join(', ') || '–';

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      state = await api('GET', '/api/training/me');
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function historyHtml(reports) {
    if (!reports.length) return App.emptyHtml(t('c_empty'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr>
      <th>${esc(t('th_date'))}</th><th class="c">${esc(t('th_hours'))}</th><th>${esc(t('th_area'))}</th>
      <th>${esc(t('f_station'))}</th><th>${esc(t('th_learned'))}</th><th>${esc(t('th_entered'))}</th><th></th></tr></thead><tbody>
      ${reports.map(r => `<tr><td class="nw">${esc(fmtDate(r.period))}</td><td class="c">${esc(fmtNum(r.hours))}</td>
        <td>${esc(area(r))}</td><td>${esc(r.station || '–')}</td><td class="wrap">${esc(r.learned || '–')}</td>
        <td class="nw">${esc(fmtDateTime(r.created_at))}</td>
        <td class="nw">${r.editable ? `<button class="btn ghost sm" type="button" data-action="edit" data-id="${r.id}">${esc(t('edit'))}</button>`
          : `<span class="mut" title="${esc(t('c_locked'))}">${App.icon('lock')}<span class="sr-only">${esc(t('c_locked'))}</span></span>`}</td></tr>`).join('')}
      </tbody></table></div>`;
  }

  function render() {
    const {trainee, reports} = state;
    const editing = editId ? reports.find(r => r.id === editId) : null;
    host.innerHTML = `
      <div class="card hero"><h2>${esc(t('c_hi', {name: trainee.nickname || trainee.name}))}</h2>
        <p>${esc(t('c_welcome'))}</p>
        ${trainee.abteilung ? `<span class="badge">${esc(trainee.abteilung)}</span>` : ''}
        ${trainee.fach ? `<span class="badge">${esc(trainee.fach)}</span>` : ''}
        <span class="badge">${esc(t('c_total', {n: fmtNum(state.summary.hours_total)}))}</span></div>
      <div class="card"><h3>${esc(t(editing ? 'c_form_edit' : 'c_form_title'))}</h3>${ReportForm.html(editing, {cancel: !!editing})}</div>
      <div class="card"><h3>${esc(t('c_hist_title', {n: reports.length}))}</h3>
        <p class="hint">${esc(t('c_edit_hint'))}</p>${historyHtml(reports)}</div>`;
    $('#report-form').addEventListener('submit', submit);
  }

  async function submit(ev) {
    ev.preventDefault();
    if (!await ReportForm.submit(ev.target, editId)) return;
    editId = null;
    toast(t('saved'));
    await load();
  }

  App.onActions(host, {
    edit: id => { editId = id; render(); window.scrollTo({top: 0, behavior: 'smooth'}); },
    cancel: () => { editId = null; render(); },
  });
  App.onRerender(() => state && render());
  load();
})();

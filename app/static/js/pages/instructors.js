/* Dozentenverwaltung: Liste mit Suche, Niveaus, Verfuegbarkeit; Anlegen/Bearbeiten/Archivieren. */
(() => {
  const {$, esc, t, can, api, toast} = App;
  const host = $('#page');
  const state = {q: '', status: '', archived: false};
  let rows = null;
  let levels = [];

  function matches(i) {
    const q = state.q.toLowerCase();
    return (!state.status || i.status === state.status)
      && (!q || [i.name, i.email, i.msh_user, i.specialization].some(v => v && v.toLowerCase().includes(q)));
  }

  function rowHtml(i) {
    const manage = can('instructor.manage');
    const login = i.msh_user ? `${esc(i.msh_user)}${i.has_instructor_role === false
      ? ` <span class="badge warn" title="${esc(t('in_no_role_hint'))}">${esc(t('in_no_role'))}</span>` : ''}` : '–';
    return `<tr${i.archived_at ? ' class="archived"' : ''}>
      <td class="name"><b>${esc(i.name)}</b>${i.email ? `<div class="meta">${esc(i.email)}</div>` : ''}</td>
      <td>${login}</td>
      <td class="nw">${i.levels.length ? i.levels.map(l => `<span class="badge">${esc(l.code)}</span>`).join(' ') : '–'}</td>
      <td class="wrap">${esc(i.specialization || '–')}${i.qualification ? `<div class="meta">${esc(i.qualification)}</div>` : ''}</td>
      <td>${esc(InstructorForm.weekText(i.availability))}</td>
      <td>${InstructorForm.statusBadge(i.status)}</td>
      <td class="c">${can('schedule.view') && i.course_count ? `<a href="/courses?instructor_id=${i.id}">${i.course_count}</a>` : i.course_count}</td>
      <td>${manage ? `<div class="row-actions">
        ${i.archived_at ? '' : `<button class="btn ghost sm" type="button" data-action="edit" data-id="${i.id}">${esc(t('edit'))}</button>`}
        <button class="btn ${i.archived_at ? 'ghost' : 'danger'} sm" type="button" data-action="${i.archived_at ? 'restore' : 'archive'}" data-id="${i.id}">${esc(t(i.archived_at ? 'btn_restore' : 'btn_archive'))}</button>
      </div>` : ''}</td></tr>`;
  }

  function renderShell() {
    host.innerHTML = `<div class="card">
      <form class="filters" role="search">
        <input class="input" type="search" name="q" value="${esc(state.q)}" placeholder="${esc(t('in_search_ph'))}" aria-label="${esc(t('in_search_ph'))}">
        <select class="input" name="status" aria-label="${esc(t('f_status'))}"><option value="">${esc(t('cl_all_status'))}</option>
          ${InstructorForm.STATUSES.map(s => `<option value="${s}"${s === state.status ? ' selected' : ''}>${esc(t('is_' + s))}</option>`).join('')}</select>
        <label class="meta"><input type="checkbox" name="archived"${state.archived ? ' checked' : ''}> ${esc(t('tm_show_archived'))}</label>
      </form>
      <div id="results" aria-live="polite"></div></div>`;
  }

  function renderResults() {
    const shown = rows.filter(matches);
    $('#results').innerHTML = `<div class="pghead"><span class="meta">${esc(t('in_count', {n: shown.length}))}</span>
      ${can('instructor.manage') ? `<div class="tools"><button class="btn sm" type="button" data-action="add">${esc(t('in_add'))}</button></div>` : ''}</div>
      ${shown.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>
        <th>${esc(t('f_name'))}</th><th>${esc(t('f_login'))}</th><th>${esc(t('th_levels'))}</th><th>${esc(t('f_specialization'))}</th>
        <th>${esc(t('f_availability'))}</th><th>${esc(t('f_status'))}</th><th class="c">${esc(t('nav_courses'))}</th><th>${esc(t('th_actions'))}</th>
      </tr></thead><tbody>${shown.map(rowHtml).join('')}</tbody></table></div>`
      : App.emptyHtml(t(rows.length ? 'cl_no_match' : 'in_empty'))}`;
  }

  async function load() {
    const box = $('#results');
    box.innerHTML = App.loadingHtml();
    try {
      rows = (await api('GET', `/api/instructors${state.archived ? '?archived=1' : ''}`)).instructors;
      renderResults();
    } catch (err) {
      App.showError(box, err, load);
    }
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      levels = (await api('GET', '/api/catalogs/language-level')).entries;
    } catch (err) {
      App.showError(host, err, init);
      return;
    }
    renderShell();
    load();
  }

  async function post(url) {
    try { await api('POST', url); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
  }

  host.addEventListener('input', ev => { if (ev.target.name === 'q' && rows) { state.q = ev.target.value.trim(); renderResults(); } });
  host.addEventListener('change', ev => {
    if (ev.target.name === 'status') { state.status = ev.target.value; renderResults(); }
    if (ev.target.name === 'archived') { state.archived = ev.target.checked; load(); }
  });
  host.addEventListener('submit', ev => ev.preventDefault());
  App.onActions(host, {
    add: () => InstructorForm.open({levels, onSaved: load}),
    edit: id => InstructorForm.open({instructor: rows.find(i => i.id === id), levels, onSaved: load}),
    archive: async id => {
      const i = rows.find(r => r.id === id);
      if (await App.confirmDialog(t('in_confirm_archive', {name: i.name}))) await post(`/api/instructors/${id}/archive`);
    },
    restore: id => post(`/api/instructors/${id}/restore`),
  });
  App.onRerender(() => { if (levels.length) { renderShell(); if (rows) renderResults(); } });
  init();
})();

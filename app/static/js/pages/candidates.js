/* Candidate list: search, filter, sorting, pages (all server-side).
   The state lives in the URL — "Back" from the profile lands in the same search. */
(() => {
  const {$, esc, t, can, api, fmtDateTime} = App;
  const host = $('#page');
  const PER_PAGE = 25;
  const COLUMNS = [  // [sort-key|null, i18n-key]
    ['name', 'f_name'], ['candidate_no', 'f_candidate_no'], ['level', 'th_level'], ['status', 'f_status'],
    [null, 'at_rate'], [null, 'f_fach'], [null, 'f_instructor'], ['last_rating', 'th_last_rating'], ['last_report', 'th_last'],
  ];
  const params = new URLSearchParams(location.search);
  const state = {
    q: params.get('q') || '', status_id: params.get('status_id') || '', level_id: params.get('level_id') || '',
    fach: params.get('fach') || '', archived: params.get('archived') === '1',
    sort: params.get('sort') || 'name', page: +params.get('page') || 1,
  };
  let cats = null;
  let result = null;
  let searchTimer = null;

  function queryString() {
    const p = new URLSearchParams();
    for (const key of ['q', 'status_id', 'level_id', 'fach']) if (state[key]) p.set(key, state[key]);
    if (state.archived) p.set('archived', '1');
    if (state.sort !== 'name') p.set('sort', state.sort);
    if (state.page > 1) p.set('page', String(state.page));
    return p.toString();
  }

  function selectHtml(name, allKey, entries, current) {
    return `<select class="input" name="${name}" aria-label="${esc(t(allKey))}"><option value="">${esc(t(allKey))}</option>
      ${entries.map(e => `<option value="${esc(e.value)}"${e.value === current ? ' selected' : ''}>${esc(e.label)}</option>`).join('')}</select>`;
  }

  function renderShell() {
    const toEntries = list => list.map(e => ({value: String(e.id), label: e.name + (e.active ? '' : ' ' + t('opt_inactive'))}));
    host.innerHTML = `<div class="card">
      <form class="filters" role="search">
        <input class="input" type="search" name="q" value="${esc(state.q)}" placeholder="${esc(t('cl_search_ph'))}" aria-label="${esc(t('cl_search'))}">
        ${selectHtml('status_id', 'cl_all_status', toEntries(cats.status), state.status_id)}
        ${selectHtml('level_id', 'cl_all_levels', toEntries(cats.level), state.level_id)}
        ${selectHtml('fach', 'cl_all_fach', CandidateForm.FACH.map(f => ({value: f, label: f})), state.fach)}
        <label class="meta"><input type="checkbox" name="archived"${state.archived ? ' checked' : ''}> ${esc(t('tm_show_archived'))}</label>
      </form>
      <div id="results" aria-live="polite"></div>
    </div>`;
  }

  function headerHtml() {
    const [key, desc] = [state.sort.replace('-', ''), state.sort.startsWith('-')];
    return COLUMNS.map(([sortKey, label]) => {
      if (!sortKey) return `<th>${esc(t(label))}</th>`;
      const active = sortKey === key;
      const aria = active ? (desc ? 'descending' : 'ascending') : 'none';
      return `<th aria-sort="${aria}"><button class="sort" type="button" data-action="sort" data-sort="${sortKey}"
        title="${esc(t('sort_by', {name: t(label)}))}">${esc(t(label))}${active ? (desc ? ' ▼' : ' ▲') : ''}</button></th>`;
    }).join('');
  }

  /* Instructors from the candidate's courses, without duplicates. */
  const instructorNames = c => [...new Set(c.courses.filter(k => k.instructor).map(k => k.instructor.name))].join(', ');

  function rowHtml(c) {
    const level = c.current_level ? esc(c.current_level.code) + (c.target_level ? ` → ${esc(c.target_level.code)}` : '') : '–';
    return `<tr${c.archived_at ? ' class="archived"' : ''}>
      <td class="name"><a href="/candidates/${c.id}">${esc(c.name)}</a>${c.nickname ? ` <span class="mut">(${esc(c.nickname)})</span>` : ''}</td>
      <td class="nw">${esc(c.candidate_no)}</td><td class="nw">${level}</td>
      <td>${c.status ? `<span class="badge">${esc(c.status.name)}</span>` : '–'}</td>
      <td class="c nw">${esc(AttendanceForm.rateText(c.attendance_rate))}</td>
      <td>${esc(c.fach || '–')}${c.abteilung ? `<div class="meta">${esc(c.abteilung)}</div>` : ''}</td>
      <td>${esc(instructorNames(c) || '–')}</td>
      <td class="nw">${esc(fmtDateTime(c.last_rating_at))}</td><td class="nw">${esc(fmtDateTime(c.last_report_at))}</td></tr>`;
  }

  function renderResults() {
    const box = $('#results');
    const pages = Math.max(1, Math.ceil(result.total / result.per_page));
    const filtered = state.q || state.status_id || state.level_id || state.fach || state.archived;
    box.innerHTML = `<div class="pghead"><span class="meta">${esc(t('cl_count', {n: result.total}))}</span>
      ${can('candidate.create') ? `<div class="tools"><button class="btn sm" type="button" data-action="add">${esc(t('cl_add'))}</button></div>` : ''}</div>
      ${result.items.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>${headerHtml()}</tr></thead>
        <tbody>${result.items.map(rowHtml).join('')}</tbody></table></div>
        ${pages > 1 ? `<nav class="pager" aria-label="${esc(t('cl_page', {p: state.page, n: pages}))}">
          <button class="btn ghost sm" type="button" data-action="page" data-id="${state.page - 1}"${state.page <= 1 ? ' disabled' : ''}>${esc(t('cl_prev'))}</button>
          <span class="meta">${esc(t('cl_page', {p: state.page, n: pages}))}</span>
          <button class="btn ghost sm" type="button" data-action="page" data-id="${state.page + 1}"${state.page >= pages ? ' disabled' : ''}>${esc(t('cl_next'))}</button>
        </nav>` : ''}` : App.emptyHtml(t(filtered ? 'cl_no_match' : 'cl_empty'))}`;
  }

  async function loadResults() {
    const box = $('#results');
    box.innerHTML = App.loadingHtml();
    const qs = queryString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
    try {
      result = await api('GET', `/api/candidates?${qs}&per_page=${PER_PAGE}`);
      renderResults();
    } catch (err) {
      App.showError(box, err, loadResults);
    }
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      cats = await CandidateForm.loadCatalogs();
    } catch (err) {
      App.showError(host, err, init);
      return;
    }
    renderShell();
    loadResults();
  }

  host.addEventListener('input', ev => {
    if (ev.target.name !== 'q') return;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = ev.target.value.trim(); state.page = 1; loadResults(); }, 300);
  });
  host.addEventListener('change', ev => {
    const el = ev.target;
    if (!['status_id', 'level_id', 'fach', 'archived'].includes(el.name)) return;
    state[el.name] = el.type === 'checkbox' ? el.checked : el.value;
    state.page = 1;
    loadResults();
  });
  host.addEventListener('submit', ev => ev.preventDefault());
  App.onActions(host, {
    add: () => CandidateForm.open(null, saved => App.goWithToast(`/candidates/${saved.id}`, t('saved'))),
    sort: (_, el) => {
      const key = el.dataset.sort;
      state.sort = state.sort === key ? '-' + key : key;
      state.page = 1;
      loadResults();
    },
    page: target => { state.page = target; loadResults(); },
  });
  App.onRerender(() => { if (cats) { renderShell(); if (result) renderResults(); } });
  init();
})();

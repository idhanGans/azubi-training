/* Kursliste: Filter nach Niveau, Dozent, Status; Anlegen. Dozenten sehen nur ihre eigenen Kurse. */
(() => {
  const {$, esc, t, can, api} = App;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const state = {level_id: params.get('level_id') || '', instructor_id: params.get('instructor_id') || '',
                 status: params.get('status') || '', archived: params.get('archived') === '1'};
  let levels = [];
  let instructors = [];
  let courses = null;

  function queryString() {
    const p = new URLSearchParams();
    for (const key of ['level_id', 'instructor_id', 'status']) if (state[key]) p.set(key, state[key]);
    if (state.archived) p.set('archived', '1');
    return p.toString();
  }

  const select = (name, allKey, entries) => `<select class="input" name="${name}" aria-label="${esc(t(allKey))}">
    <option value="">${esc(t(allKey))}</option>${entries.map(e => `<option value="${esc(e.value)}"${e.value === state[name] ? ' selected' : ''}>${esc(e.label)}</option>`).join('')}</select>`;

  function renderShell() {
    host.innerHTML = `<div class="card">
      <form class="filters" role="search">
        ${select('level_id', 'cl_all_levels', levels.map(l => ({value: String(l.id), label: l.name})))}
        ${instructors.length ? select('instructor_id', 'co_all_instructors', instructors.map(i => ({value: String(i.id), label: i.name}))) : ''}
        ${select('status', 'cl_all_status', CourseForm.STATUSES.map(s => ({value: s, label: t('cs_' + s)})))}
        <label class="meta"><input type="checkbox" name="archived"${state.archived ? ' checked' : ''}> ${esc(t('tm_show_archived'))}</label>
      </form>
      <div id="results" aria-live="polite"></div></div>`;
  }

  function rowHtml(c) {
    return `<tr${c.archived_at ? ' class="archived"' : ''}>
      <td class="name"><a href="/courses/${c.id}">${esc(c.name)}</a></td>
      <td class="nw"><span class="badge">${esc(c.level.code)}</span></td>
      <td>${c.module ? esc(c.module.name) + `<div class="meta">${esc(c.module.program)}</div>` : '–'}</td>
      <td>${c.instructor ? esc(c.instructor.name) : `<span class="mut">${esc(t('co_no_instructor'))}</span>`}</td>
      <td class="c">${c.participant_count}</td><td>${CourseForm.statusBadge(c.status)}</td></tr>`;
  }

  function renderResults() {
    const filtered = state.level_id || state.instructor_id || state.status || state.archived;
    $('#results').innerHTML = `<div class="pghead"><span class="meta">${esc(t('co_count', {n: courses.length}))}</span>
      ${can('schedule.create') ? `<div class="tools"><button class="btn sm" type="button" data-action="add">${esc(t('co_add'))}</button></div>` : ''}</div>
      ${courses.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_name'))}</th><th>${esc(t('th_level'))}</th>
        <th>${esc(t('f_current_module'))}</th><th>${esc(t('f_instructor'))}</th><th class="c">${esc(t('th_participants'))}</th>
        <th>${esc(t('f_status'))}</th></tr></thead><tbody>${courses.map(rowHtml).join('')}</tbody></table></div>`
      : App.emptyHtml(t(filtered ? 'cl_no_match' : 'co_empty'))}`;
  }

  async function load() {
    const box = $('#results');
    box.innerHTML = App.loadingHtml();
    const qs = queryString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
    try {
      courses = (await api('GET', `/api/courses?${qs}`)).courses;
      renderResults();
    } catch (err) {
      App.showError(box, err, load);
    }
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      const [lv, inst] = await Promise.all([api('GET', '/api/catalogs/language-level'),
        can('instructor.view') ? api('GET', '/api/instructors') : Promise.resolve({instructors: []})]);
      levels = lv.entries;
      instructors = inst.instructors;
    } catch (err) {
      App.showError(host, err, init);
      return;
    }
    renderShell();
    load();
  }

  host.addEventListener('change', ev => {
    const el = ev.target;
    if (!['level_id', 'instructor_id', 'status', 'archived'].includes(el.name)) return;
    state[el.name] = el.type === 'checkbox' ? el.checked : el.value;
    load();
  });
  host.addEventListener('submit', ev => ev.preventDefault());
  App.onActions(host, {
    add: () => CourseForm.open({levels, onSaved: saved => App.goWithToast(`/courses/${saved.id}`, t('saved'))})
      .catch(err => App.toast(err.message, 'error')),
  });
  App.onRerender(() => { if (levels.length) { renderShell(); if (courses) renderResults(); } });
  init();
})();

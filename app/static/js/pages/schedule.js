/* Stundenplan: Kalender Tag / Woche / Monat mit Filtern (Dozent, Kandidat, Niveau, Modul, Kurs).
   Zustand in der URL, damit Links wie /schedule?course_id=3 funktionieren. */
(() => {
  const {$, esc, t, can, api, days, todayIso} = App;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const FILTERS = ['course_id', 'instructor_id', 'trainee_id', 'level_id', 'module_id'];
  const state = {view: ['day', 'week', 'month'].includes(params.get('view')) ? params.get('view') : 'week',
                 date: /^\d{4}-\d{2}-\d{2}$/.test(params.get('date') || '') ? params.get('date') : todayIso(),
                 cancelled: params.get('cancelled') === '1'};
  FILTERS.forEach(f => { state[f] = params.get(f) || ''; });
  const opts = {courses: [], instructors: [], trainees: [], levels: [], modules: []};
  let sessions = null;

  function range() {
    if (state.view === 'day') return [state.date, state.date];
    if (state.view === 'week') { const mon = days.monday(state.date); return [mon, days.add(mon, 6)]; }
    const first = days.monday(days.monthStart(state.date));               // volle Wochen im Monatsraster
    const last = days.add(days.addMonths(days.monthStart(state.date), 1), -1);
    return [first, days.add(days.monday(last), 6)];
  }

  function title() {
    if (state.view === 'day') return days.label(state.date, {weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric'});
    if (state.view === 'week') {
      const [a, b] = range();
      return `${App.fmtDate(a)} – ${App.fmtDate(b)}`;
    }
    return days.label(state.date, {month: 'long', year: 'numeric'});
  }

  function queryString() {
    const p = new URLSearchParams();
    if (state.view !== 'week') p.set('view', state.view);
    if (state.date !== todayIso()) p.set('date', state.date);
    FILTERS.forEach(f => { if (state[f]) p.set(f, state[f]); });
    if (state.cancelled) p.set('cancelled', '1');
    return p.toString();
  }

  const select = (name, allKey, entries) => `<select class="input" name="${name}" aria-label="${esc(t(allKey))}">
    <option value="">${esc(t(allKey))}</option>${entries.map(e => `<option value="${esc(e.value)}"${e.value === state[name] ? ' selected' : ''}>${esc(e.label)}</option>`).join('')}</select>`;

  function renderShell() {
    const views = ['day', 'week', 'month'].map(v => `<button type="button" class="btn ${state.view === v ? '' : 'ghost'} sm" data-action="view" data-view="${v}" aria-pressed="${state.view === v}">${esc(t('cal_' + v))}</button>`).join('');
    host.innerHTML = `<div class="card">
      <div class="cal-toolbar">
        <div class="cal-nav">
          <button class="btn ghost sm" type="button" data-action="step" data-id="-1" aria-label="${esc(t('cal_prev'))}">${App.icon('chevron-left')}</button>
          <button class="btn ghost sm" type="button" data-action="today">${esc(t('cal_today'))}</button>
          <button class="btn ghost sm" type="button" data-action="step" data-id="1" aria-label="${esc(t('cal_next'))}">${App.icon('chevron-right')}</button>
          <h2 class="cal-title" aria-live="polite">${esc(title())}</h2>
        </div>
        <div class="tools"><div class="seg" role="group" aria-label="${esc(t('cal_view'))}">${views}</div>
          ${can('schedule.create') ? `<button class="btn sm" type="button" data-action="add">${esc(t('se_add'))}</button>` : ''}</div>
      </div>
      <form class="filters" role="search">
        ${select('course_id', 'cal_all_courses', opts.courses.map(c => ({value: String(c.id), label: c.name})))}
        ${opts.instructors.length ? select('instructor_id', 'co_all_instructors', opts.instructors.map(i => ({value: String(i.id), label: i.name}))) : ''}
        ${select('trainee_id', 'cal_all_candidates', opts.trainees.map(c => ({value: String(c.id), label: c.name})))}
        ${select('level_id', 'cl_all_levels', opts.levels.map(l => ({value: String(l.id), label: l.name})))}
        ${state.level_id ? select('module_id', 'cal_all_modules', opts.modules.map(m => ({value: String(m.id), label: m.name}))) : ''}
        <label class="meta"><input type="checkbox" name="cancelled"${state.cancelled ? ' checked' : ''}> ${esc(t('cal_show_cancelled'))}</label>
      </form>
      <div id="cal" aria-live="polite"></div></div>`;
  }

  function byDay() {
    const map = {};
    sessions.forEach(s => { (map[s.date] = map[s.date] || []).push(s); });
    return map;
  }

  function renderDay() {
    const list = byDay()[state.date] || [];
    return list.length ? `<div class="sess-list">${list.map(s => SessionForm.cardHtml(s)).join('')}</div>` : App.emptyHtml(t('cal_empty_day'));
  }

  function renderWeek() {
    const [mon] = range(), map = byDay(), today = todayIso();
    return `<div class="cal-week">${[0, 1, 2, 3, 4, 5, 6].map(i => {
      const d = days.add(mon, i), list = map[d] || [];
      return `<section class="cal-col${d === today ? ' today' : ''}" aria-label="${esc(days.label(d, {weekday: 'long', day: '2-digit', month: '2-digit'}))}">
        <h3><button type="button" class="lnk" data-action="goto" data-date="${d}">${esc(days.label(d, {weekday: 'short', day: '2-digit', month: '2-digit'}))}</button></h3>
        ${list.map(s => SessionForm.cardHtml(s)).join('') || `<span class="meta">–</span>`}</section>`;
    }).join('')}</div>`;
  }

  function renderMonth() {
    const [first, last] = range(), map = byDay(), today = todayIso(), month = state.date.slice(0, 7);
    const heads = [0, 1, 2, 3, 4, 5, 6].map(i => `<div class="cal-head">${esc(days.label(days.add(first, i), {weekday: 'short'}))}</div>`).join('');
    const cells = [];
    for (let d = first; d <= last; d = days.add(d, 1)) {
      const list = map[d] || [];
      cells.push(`<div class="cal-cell${d.slice(0, 7) !== month ? ' other' : ''}${d === today ? ' today' : ''}">
        <button type="button" class="lnk cal-num" data-action="goto" data-date="${d}" aria-label="${esc(App.fmtDate(d))}">${+d.slice(8)}</button>
        ${list.slice(0, 3).map(s => `<button type="button" class="chip${s.status === 'CANCELLED' ? ' cancelled' : ''}" data-action="session" data-id="${s.id}" title="${esc(s.start)} ${esc(s.course.name)}">${esc(s.start)}<span class="chip-name"> ${esc(s.course.name)}</span></button>`).join('')}
        ${list.length > 3 ? `<button type="button" class="lnk meta" data-action="goto" data-date="${d}">${esc(t('cal_more', {n: list.length - 3}))}</button>` : ''}
      </div>`);
    }
    return `<div class="cal-month">${heads}${cells.join('')}</div>`;
  }

  function renderCal() {
    const box = $('#cal');
    const body = state.view === 'day' ? renderDay() : state.view === 'week' ? renderWeek() : renderMonth();
    box.innerHTML = `<p class="meta">${esc(t('cal_count', {n: sessions.length}))}</p>${body}`;
  }

  async function load() {
    const box = $('#cal');
    box.innerHTML = App.loadingHtml();
    const qs = queryString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
    const [from, to] = range();
    const p = new URLSearchParams({from, to});
    FILTERS.forEach(f => { if (state[f]) p.set(f, state[f]); });
    if (state.cancelled) p.set('include_cancelled', '1');
    try {
      sessions = (await api('GET', `/api/sessions?${p}`)).sessions;
      renderCal();
    } catch (err) {
      App.showError(box, err, load);
    }
  }

  async function loadModules() {
    opts.modules = state.level_id && can('curriculum.view') ? (await api('GET', `/api/modules?level_id=${state.level_id}`)).modules : [];
  }

  async function allCandidates() {
    const items = [];
    for (let page = 1; ; page++) {
      const res = await api('GET', `/api/candidates?per_page=100&page=${page}`);
      items.push(...res.items);
      if (items.length >= res.total || !res.items.length) return items;
    }
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      const [courses, instructors, trainees, levels] = await Promise.all([
        api('GET', '/api/courses'),
        can('instructor.view') ? api('GET', '/api/instructors') : Promise.resolve({instructors: []}),
        can('candidate.view') ? allCandidates() : Promise.resolve([]),
        api('GET', '/api/catalogs/language-level')]);
      opts.courses = courses.courses;
      opts.instructors = instructors.instructors;
      opts.trainees = trainees;
      opts.levels = levels.entries;
      await loadModules();
    } catch (err) {
      App.showError(host, err, init);
      return;
    }
    renderShell();
    load();
  }

  function step(n) {
    if (state.view === 'day') state.date = days.add(state.date, n);
    else if (state.view === 'week') state.date = days.add(state.date, 7 * n);
    else state.date = days.addMonths(state.date, n);
    renderShell();
    load();
  }

  host.addEventListener('change', async ev => {
    const el = ev.target;
    if (el.name === 'cancelled') state.cancelled = el.checked;
    else if (FILTERS.includes(el.name)) state[el.name] = el.value;
    else return;
    if (el.name === 'level_id') {
      state.module_id = '';
      try { await loadModules(); } catch (err) { App.toast(err.message, 'error'); }
      renderShell();
    }
    load();
  });
  host.addEventListener('submit', ev => ev.preventDefault());
  App.onActions(host, {
    view: (_, el) => { state.view = el.dataset.view; renderShell(); load(); },
    step: n => step(n),
    today: () => { state.date = todayIso(); renderShell(); load(); },
    goto: (_, el) => { state.view = 'day'; state.date = el.dataset.date; renderShell(); load(); },
    session: id => SessionForm.show(sessions.find(s => s.id === id), {onChanged: load, courses: opts.courses}),
    add: () => SessionForm.open({courses: opts.courses, date: state.view === 'day' ? state.date : '',
                                 onSaved: load}).catch(err => App.toast(err.message, 'error')),
  });
  App.onRerender(() => { if (sessions) { renderShell(); renderCal(); } });
  init();
})();

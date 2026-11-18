/* Berichte: Anwesenheit, Leistung, Dozenten (Tabellen + CSV) und Einstieg in den Kandidatenbericht.
   Eine Filterzeile (Zeitraum, Kurs, Niveau) gilt fuer alles darunter; Zustand steht in der URL. */
(() => {
  const {$, esc, t, api, fmtNum, todayIso, days} = App;
  const host = $('#page');
  const TABS = ['attendance', 'academic', 'instructors', 'candidate'];
  const params = new URLSearchParams(location.search);
  const state = {tab: TABS.includes(params.get('tab')) ? params.get('tab') : 'attendance',
                 preset: params.get('preset') || (params.get('from') ? 'custom' : '90'),
                 from: params.get('from') || '', to: params.get('to') || '',
                 course_id: params.get('course_id') || '', level_id: params.get('level_id') || ''};
  let courses = [], levels = [], data = null, sort = null, candidates = [];

  function period() {
    const today = todayIso();
    switch (state.preset) {
      case '30': return {from: days.add(today, -29), to: today};
      case '90': return {from: days.add(today, -89), to: today};
      case 'month': return {from: days.monthStart(today), to: today};
      case 'last_month': { const start = days.addMonths(today, -1); return {from: start, to: days.add(days.monthStart(today), -1)}; }
      case 'year': return {from: today.slice(0, 4) + '-01-01', to: today};
      default: return {from: state.from || days.add(today, -89), to: state.to || today};
    }
  }

  function query(extra) {
    const p = new URLSearchParams(period());
    if (state.tab !== 'instructors') {
      if (state.course_id) p.set('course_id', state.course_id);
      if (state.level_id) p.set('level_id', state.level_id);
    }
    Object.entries(extra || {}).forEach(([k, v]) => p.set(k, v));
    return p.toString();
  }

  function syncUrl() {
    const p = new URLSearchParams({tab: state.tab, preset: state.preset});
    if (state.preset === 'custom') { p.set('from', state.from); p.set('to', state.to); }
    if (state.course_id) p.set('course_id', state.course_id);
    if (state.level_id) p.set('level_id', state.level_id);
    history.replaceState(null, '', `${location.pathname}?${p}`);
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      const [c, l] = await Promise.all([api('GET', '/api/courses'), api('GET', '/api/catalogs/language-level')]);
      courses = c.courses;
      levels = l.entries;
      renderFrame();
      await load();
    } catch (err) {
      App.showError(host, err, init);
    }
  }

  function renderFrame() {
    const opt = (v, label, cur) => `<option value="${esc(v)}"${String(v) === String(cur) ? ' selected' : ''}>${esc(label)}</option>`;
    const p = period();
    host.innerHTML = `<div class="tabs no-print" role="tablist">${TABS.map(tab => `<button type="button" role="tab" data-tab="${tab}"
        aria-selected="${tab === state.tab}">${esc(t('rp_tab_' + tab))}</button>`).join('')}</div>
      <div class="card filters no-print">
        <label class="meta">${esc(t('rp_period'))}
          <select class="input" name="preset">${['30', '90', 'month', 'last_month', 'year', 'custom'].map(v => opt(v, t('rp_preset_' + v), state.preset)).join('')}</select></label>
        <label class="meta"${state.preset === 'custom' ? '' : ' hidden'} data-custom>${esc(t('rp_from'))}<input class="input" type="date" name="from" value="${esc(p.from)}"></label>
        <label class="meta"${state.preset === 'custom' ? '' : ' hidden'} data-custom>${esc(t('rp_to'))}<input class="input" type="date" name="to" value="${esc(p.to)}"></label>
        <label class="meta" data-scope>${esc(t('f_course'))}<select class="input" name="course_id">${opt('', t('rp_all_courses'), state.course_id)}
          ${courses.map(c => opt(c.id, c.name, state.course_id)).join('')}</select></label>
        <label class="meta" data-scope>${esc(t('th_level'))}<select class="input" name="level_id">${opt('', t('rp_all_levels'), state.level_id)}
          ${levels.map(x => opt(x.id, x.name, state.level_id)).join('')}</select></label>
        <button class="btn ghost sm" type="button" data-print>${esc(t('rp_print'))}</button>
      </div>
      <p class="meta print-only" data-period></p>
      <div id="report"></div>`;
    host.querySelectorAll('[data-scope]').forEach(el => { el.hidden = state.tab === 'instructors' || state.tab === 'candidate'; });
    host.querySelector('[data-print]').hidden = state.tab === 'candidate';
  }

  async function load() {
    syncUrl();
    const target = $('#report');
    if (state.tab === 'candidate') { renderCandidatePicker(target); return; }
    target.classList.add('refreshing');
    if (!data) target.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', `/api/reports/${state.tab}?${query()}`);
      target.classList.remove('refreshing');
      renderReport();
    } catch (err) {
      target.classList.remove('refreshing');
      App.showError(target, err, load);
    }
  }

  function tile(value, key) { return `<div class="stat"><b>${esc(value)}</b><span>${esc(t(key))}</span></div>`; }
  const pct = v => (v == null ? '–' : `${fmtNum(v, 1)} %`);

  function summaryHtml() {
    const s = data.summary;
    if (state.tab === 'attendance') {
      return tile(s.candidates, 'db_candidates') + tile(s.attendance ? pct(s.attendance.rate == null ? null : s.attendance.rate * 100) : '–', 'at_rate')
        + tile(s.absences, 'rp_absences') + tile(s.late, 'rp_late');
    }
    if (state.tab === 'academic') {
      return tile(s.candidates, 'db_candidates') + tile(s.assessments, 'rp_assessments')
        + tile(pct(s.avg_latest), 'db_avg_assessment') + tile(s.pass_rate == null ? '–' : pct(s.pass_rate * 100), 'rp_pass_rate');
    }
    return tile(s.instructors, 'nav_instructors') + tile(`${fmtNum(s.hours_held, 1)} h`, 'rp_hours_held')
      + tile(s.assessments_final, 'rp_assessments_final') + tile(s.assessments_open, 'db_open_assessments');
  }

  function renderReport() {
    const p = data.period;
    host.querySelector('[data-period]').textContent = `${t('rp_tab_' + state.tab)} · ${App.fmtDate(p.from)} – ${App.fmtDate(p.to)}`;
    $('#report').innerHTML = `<div class="stats">${summaryHtml()}</div>
      ${data.tables.map(tb => ReportTable.html(tb, `/api/reports/${state.tab}?${query({format: 'csv', table: tb.id})}`, sort)).join('')}`;
  }

  function renderCandidatePicker(target) {
    target.innerHTML = `<section class="card"><h3>${esc(t('rp_tab_candidate'))}</h3><p class="hint">${esc(t('rp_candidate_hint'))}</p>
      <div class="filters"><input class="input" type="search" name="q" placeholder="${esc(t('as_search_ph'))}" aria-label="${esc(t('as_candidate_search'))}"></div>
      <ul class="plain" data-results></ul></section>`;
    const list = target.querySelector('[data-results]');
    let timer = null;
    async function search(q) {
      try {
        candidates = (await api('GET', `/api/candidates?per_page=20&sort=name${q ? '&q=' + encodeURIComponent(q) : ''}`)).items;
        list.innerHTML = candidates.length ? candidates.map(c => `<li><a href="/reports/candidates/${c.id}">${esc(c.name)}</a>
          <span class="meta">${esc(c.candidate_no)}${c.abteilung ? ' · ' + esc(c.abteilung) : ''}</span></li>`).join('') : `<li>${esc(t('cl_no_match'))}</li>`;
      } catch (err) { App.showError(list, err); }
    }
    target.querySelector('[name="q"]').addEventListener('input', ev => { clearTimeout(timer); timer = setTimeout(() => search(ev.target.value.trim()), 250); });
    search('');
  }

  host.addEventListener('change', ev => {
    const name = ev.target.name;
    if (!['preset', 'from', 'to', 'course_id', 'level_id'].includes(name)) return;
    if (name === 'preset' && ev.target.value === 'custom') { const p = period(); state.from = p.from; state.to = p.to; }
    state[name] = ev.target.value;
    host.querySelectorAll('[data-custom]').forEach(el => { el.hidden = state.preset !== 'custom'; });
    load();
  });
  host.addEventListener('click', ev => {
    const tab = ev.target.closest('[data-tab]');
    if (tab) { state.tab = tab.dataset.tab; data = null; sort = null; renderFrame(); load(); return; }
    const head = ev.target.closest('[data-sort]');
    if (head) {
      const [table, key] = head.dataset.sort.split('|');
      sort = sort && sort.table === table && sort.key === key ? {...sort, desc: !sort.desc} : {table, key, desc: false};
      renderReport();
      return;
    }
    if (ev.target.closest('[data-print]')) window.print();
  });
  App.onRerender(() => { renderFrame(); if (data && state.tab !== 'candidate') renderReport(); else load(); });
  init();
})();

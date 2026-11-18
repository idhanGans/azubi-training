/* Modul-Auswertung je Gruppe (Panduan Schritt 5): Durchschnitte, Trend zum Zeitraum davor, schwaechster Aspekt,
   Level-Verteilung, Begleitung (Level D) / Zusatzaufgaben (Level A), Verlauf je Termin. Zahlen kommen fertig vom
   Server; der Browser skaliert nur fuer die Diagramme (Wert / Hoechstwert). Zustand steht in der URL. */
(() => {
  const {$, esc, t, can, api, fmtDate, fmtNum, todayIso, days} = App;
  const V = LessonView;
  const host = $('#page');
  const PRESETS = ['week', 'last_week', 'month', 'last_month', 'all', 'custom'];
  const params = new URLSearchParams(location.search);
  const state = {course: params.get('course') || '', preset: PRESETS.includes(params.get('preset')) ? params.get('preset') : 'month',
                 from: params.get('from') || '', to: params.get('to') || ''};
  let courses = [], data = null;

  function period() {
    const today = todayIso();
    switch (state.preset) {
      case 'week': return {from: days.monday(today), to: today};
      case 'last_week': { const start = days.add(days.monday(today), -7); return {from: start, to: days.add(start, 6)}; }
      case 'month': return {from: days.monthStart(today), to: today};
      case 'last_month': return {from: days.addMonths(today, -1), to: days.add(days.monthStart(today), -1)};
      case 'all': return null;
      default: return {from: state.from || days.monthStart(today), to: state.to || today};
    }
  }

  function syncUrl() {
    const p = new URLSearchParams({course: state.course, preset: state.preset});
    if (state.preset === 'custom') { const x = period(); p.set('from', x.from); p.set('to', x.to); }
    history.replaceState(null, '', `${location.pathname}?${p}`);
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      courses = (await api('GET', '/api/courses')).courses.filter(c => !c.archived_at);
      if (!courses.some(c => String(c.id) === state.course)) state.course = courses.length ? String(courses[0].id) : '';
      renderFrame();
      await load();
    } catch (err) {
      App.showError(host, err, init);
    }
  }

  function renderFrame() {
    const opt = (v, label, cur) => `<option value="${esc(v)}"${String(v) === String(cur) ? ' selected' : ''}>${esc(label)}</option>`;
    const p = period() || {from: '', to: ''};
    host.innerHTML = `<div class="card filters no-print">
        <label class="meta">${esc(t('f_course'))}<select class="input" name="course">${courses.map(c => opt(c.id, c.name, state.course)).join('')}</select></label>
        <label class="meta">${esc(t('rp_period'))}<select class="input" name="preset">${PRESETS.map(v => opt(v, t('lr_preset_' + v), state.preset)).join('')}</select></label>
        <label class="meta"${state.preset === 'custom' ? '' : ' hidden'} data-custom>${esc(t('rp_from'))}<input class="input" type="date" name="from" value="${esc(p.from)}"></label>
        <label class="meta"${state.preset === 'custom' ? '' : ' hidden'} data-custom>${esc(t('rp_to'))}<input class="input" type="date" name="to" value="${esc(p.to)}"></label>
      </div><div id="result" aria-live="polite"></div>`;
    host.querySelector('.filters').addEventListener('change', ev => {
      const {name, value} = ev.target;
      if (name === 'preset' && value === 'custom') { const x = period() || {}; state.from = x.from || ''; state.to = x.to || ''; }
      if (name in state) state[name] = value;
      host.querySelectorAll('[data-custom]').forEach(el => { el.hidden = state.preset !== 'custom'; });
      load();
    });
  }

  async function load() {
    const out = $('#result');
    if (!state.course) { out.innerHTML = `<div class="card">${App.emptyHtml(t('lr_no_courses'))}</div>`; return; }
    syncUrl();
    out.innerHTML = App.loadingHtml();
    const p = period();
    try {
      data = await api('GET', `/api/courses/${state.course}/lesson-report${p ? `?${new URLSearchParams(p)}` : ''}`);
      render();
    } catch (err) {
      App.showError(out, err, load);
    }
  }

  const person = x => (can('candidate.view') ? `<a href="/candidates/${x.id}">${esc(x.name)}</a>` : esc(x.name));
  const tile = (value, label) => `<div class="stat"><b>${value}</b><span>${esc(label)}</span></div>`;

  function listCard(title, hint, list) {
    return `<section class="card"><h3>${esc(title)}</h3><p class="meta">${esc(hint)}</p>
      ${list.length ? `<ul class="plain">${list.map(x => `<li>${person(x)}</li>`).join('')}</ul>` : App.emptyHtml(t('lr_nobody'))}</section>`;
  }

  function participantsHtml() {
    const r = data.rules;
    const rows = data.participants;
    if (!rows.length) return App.emptyHtml(t('co_no_participants'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_name'))}</th><th class="c">${esc(t('lr_th_count'))}</th>
      <th class="c">${esc(t('lr_th_avg_points'))}</th><th class="c">${esc(t('lr_th_trend'))}</th><th class="c">${esc(t('lr_th_latest'))}</th>
      ${r.aspects.map(a => `<th class="c" title="${esc(V.aspectName(a))}">Ø ${esc(a.toUpperCase())}</th>`).join('')}
      ${V.BEHAVIOR.map(b => `<th class="c" title="${esc(V.behaviorName(b))}">Ø ${esc(t('lr_short_' + b))}</th>`).join('')}
      <th>${esc(t('lr_strength'))}</th><th>${esc(t('lr_target'))}</th></tr></thead>
      <tbody>${rows.map(p => { const avg = p.average, last = p.latest; return `<tr${p.trainee.in_course ? '' : ' class="archived"'}>
        <td class="name">${person(p.trainee)}${p.trainee.nickname ? ` <span class="mut">(${esc(p.trainee.nickname)})</span>` : ''}</td>
        <td class="c">${p.count}</td><td class="c">${esc(fmtNum(avg.total))}</td>
        <td class="c" title="${esc(t('lr_trend_hint', {n: fmtNum(p.previous_total)}))}">${V.trend(p.trend)}</td>
        <td class="c">${last ? V.levelBadge(last.level) : '–'}</td>
        ${r.aspects.map(a => `<td class="c">${esc(fmtNum(avg.aspects[a], 2))}</td>`).join('')}
        ${V.BEHAVIOR.map(b => `<td class="c">${esc(fmtNum(avg.behavior[b], 2))}</td>`).join('')}
        <td>${last ? esc(V.codesText(last.strength)) : '–'}</td><td>${last ? esc(V.codesText(last.target)) : '–'}</td></tr>`; }).join('')}
      </tbody></table></div>`;
  }

  function sessionsHtml() {
    if (!data.sessions.length) return App.emptyHtml(t('lr_no_data'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('th_date'))}</th><th>${esc(t('page_module'))}</th>
      <th class="c">${esc(t('lr_th_rated'))}</th><th class="c">${esc(t('lr_th_avg_points'))}</th><th></th></tr></thead>
      <tbody>${data.sessions.slice().reverse().map(x => `<tr><td class="nw">${esc(fmtDate(x.date))}</td>
        <td>${esc(x.module ? x.module.name : '–')} <span class="meta">${esc(V.unitText(x.unit))}</span></td>
        <td class="c">${x.rated}</td><td class="c">${esc(fmtNum(x.average_total))}</td>
        <td><a class="btn ghost sm" href="/sessions/${x.id}/lesson?module=${x.module.id}&unit=${x.unit}">${esc(t('lr_open'))}</a></td></tr>`).join('')}</tbody></table></div>`;
  }

  function render() {
    const out = $('#result');
    const g = data.group, r = data.rules;
    const p = data.period;
    const span = p.from ? `${fmtDate(p.from)} – ${fmtDate(p.to)}` : t('lr_preset_all');
    if (!g.count) {
      out.innerHTML = `<div class="card"><p class="meta">${esc(data.course.name)} · ${esc(span)}</p>${App.emptyHtml(t('lr_no_data'))}</div>
        ${data.participants.length ? `<section class="card"><h3>${esc(t('lr_participants'))}</h3>${participantsHtml()}</section>` : ''}`;
      return;
    }
    const levels = r.levels.map(l => `${V.levelBadge(l.code)} ${g.levels[l.code] || 0}`).join(' ');
    out.innerHTML = `<p class="hint">${esc(data.course.name)} · ${esc(span)} · ${esc(t('lr_report_hint'))}</p>
      <div class="stats">${tile(esc(String(g.count)), t('lr_th_count'))}
        ${tile(esc(`${fmtNum(g.average.total)} / ${r.total_max}`), t('lr_th_avg_points'))}
        ${tile(esc(g.weakest.map(a => a.toUpperCase()).join(', ') || '–'), t('lr_weakest'))}
        ${tile(levels, t('lr_level_dist'))}</div>
      <div class="todo-grid lr-pair">${listCard(t('lr_coaching_title'), t('lr_coaching_hint'), data.coaching)}
        ${listCard(t('lr_challenge_title'), t('lr_challenge_hint'), data.challenge)}</div>
      <section class="card"><h3>${esc(t('lr_charts'))}</h3><div id="lr-charts"></div></section>
      <section class="card"><h3>${esc(t('lr_participants'))}</h3><p class="meta">${esc(t('lr_participants_hint'))}</p>${participantsHtml()}</section>
      <section class="card"><h3>${esc(t('lr_sessions_title'))}</h3>${sessionsHtml()}</section>`;
    const charts = $('#lr-charts');
    const aspects = r.aspects.map(a => ({value: g.average.aspects[a] == null ? null : g.average.aspects[a] / r.aspect_max * 100,
      short: a.toUpperCase(), label: V.aspectName(a), valueText: fmtNum(g.average.aspects[a], 2)}));
    Charts.columns(charts, {title: t('lr_chart_aspects', {max: r.aspect_max}), points: aspects,
      table: {head: [t('lr_th_aspect'), t('lr_th_avg_stars')], rows: aspects.map(x => [x.label, x.valueText])}});
    const series = data.sessions.filter(x => x.average_total != null).map(x => ({value: x.average_total / r.total_max * 100,
      short: days.label(x.date, {day: '2-digit', month: '2-digit'}),
      label: `${fmtDate(x.date)} · ${x.module.name} ${V.unitText(x.unit)}`, valueText: fmtNum(x.average_total)}));
    if (series.length) {
      Charts.line(charts, {title: t('lr_chart_sessions', {max: r.total_max}), points: series,
        table: {head: [t('th_date'), t('lr_th_avg_points')], rows: series.map(x => [x.label, x.valueText])}});
    }
  }

  App.onRerender(() => { if (courses.length || data) { renderFrame(); if (data) render(); } });
  init();
})();

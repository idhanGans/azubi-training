/* Azubi report: the four parts of the overall rating with derivation, total, rank and ratings — Excel/PDF.
   The server returns other raters and notes only to the team; SPV/leaders see their own ratings. */
(() => {
  const {$, esc, t, api, fmtDate, fmtDateTime, fmtNum} = App;
  const V = OverallView;
  const host = $('#page');
  const id = host.dataset.traineeId;
  const state = V.readState(new URLSearchParams(location.search));
  let data = null;
  let months = null;   // month history (`/api/overall/<id>/months`) — independent of the period filter

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      [data, months] = await Promise.all([api('GET', `/api/overall/${id}?${V.query(state)}`),
                                          api('GET', `/api/overall/${id}/months`)]);
      App.setPageTitle(data.name, [{href: `/overall${location.search}`, label: t('nav_overall')}]);
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  const fact = V.fact;
  const tile = (value, label, sub) => `<div class="stat"><b>${value}</b><span>${esc(label)}</span>${sub ? `<small class="meta">${esc(sub)}</small>` : ''}</div>`;
  const categoryName = c => V.categoryName(c);

  function ratingsHtml() {
    if (!data.ratings.length) return App.emptyHtml(t(data.all_ratings ? 'cp_no_ratings' : 'ov_no_own_ratings'));
    const cats = data.rules.categories;
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th class="c">${esc(t('rt_month'))}</th><th>${esc(t('th_date'))}</th><th>${esc(t('rt_kind'))}</th>
      ${data.all_ratings ? `<th>${esc(t('th_rater'))}</th>` : ''}
      ${cats.map(c => `<th class="c">${esc(categoryName(c))}</th>`).join('')}<th>${esc(t('f_note'))}</th></tr></thead>
      <tbody>${data.ratings.map(x => `<tr><td class="c">${esc(String(x.month))}</td><td class="nw">${esc(fmtDateTime(x.created_at))}</td><td>${esc(V.kindName(x.kind))}</td>
        ${data.all_ratings ? `<td>${esc(x.rater)}</td>` : ''}${cats.map(c => `<td class="c">${x[c]}</td>`).join('')}
        <td class="wrap">${esc(x.note || '–')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  /* Month history: change of the newest comparable month pair, line chart of the total, table per part (SPV/Intern
     with their categories) — all values from the server. */
  function historyHtml() {
    const r = data.rules, step = months.latest, cols = months.history;
    const cal = m => months.calendar[m - 1];
    const head = step ? `<p class="mh-step">${V.trendBadge(step.trend)} <b>${esc(t('mh_step', {a: step.from_month, b: step.to_month,
      from: fmtNum(step.from), to: fmtNum(step.to), delta: V.signed(step.delta),
      percent: step.percent == null ? '–' : `${V.signed(step.percent)} %`}))}</b></p>
      ${step.parts.length < r.parts.length ? `<p class="meta">${esc(t('mv_compared_parts', {parts: step.parts.map(V.partName).join(', ')}))}</p>` : ''}`
      : `<p class="meta">${esc(t('mh_no_step'))}</p>`;
    const deltaOf = k => (step && step.part_deltas[k] != null ? V.signed(step.part_deltas[k]) : '–');
    const cell = v => (v == null ? `<td class="c">${V.pending()}</td>` : `<td class="c">${esc(fmtNum(v))}</td>`);
    const partial = step && step.parts.length < r.parts.length;
    const compareRow = partial ? `<tr class="total"><td>${esc(t('mh_compare_row', {parts: step.parts.map(V.partName).join(', ')}))}</td>
      ${cols.map(c => `<td class="c">${c.month === step.from_month ? esc(fmtNum(step.from)) : c.month === step.to_month ? esc(fmtNum(step.to)) : ''}</td>`).join('')}
      <td class="c">${esc(V.signed(step.delta))}</td></tr>` : '';
    const rows = [
      `<tr class="total"><td>${esc(t('ov_total'))}</td>${cols.map(c => cell(c.total)).join('')}<td class="c">${esc(step && !partial ? V.signed(step.delta) : '–')}</td></tr>`,
      compareRow,
      ...r.parts.flatMap(k => [
        `<tr><td>${esc(V.partName(k))} · ${r.weights[k]} %</td>${cols.map(c => cell(c.parts[k].score)).join('')}<td class="c">${esc(deltaOf(k))}</td></tr>`,
        ...(k === 'spv' || k === 'intern' ? r.categories.map(cat => `<tr class="sub"><td>${esc(V.categoryName(cat))}</td>
          ${cols.map(c => cell(c.parts[k][cat] ?? null)).join('')}<td class="c">–</td></tr>`) : []),
      ]),
    ];
    return `<section class="card section-gap"><h3>${esc(t('mh_title'))}</h3>${head}<div id="mh-chart"></div>
      <div class="tbl-wrap"><table class="tbl mh-table"><thead><tr><th>${esc(t('mh_part'))}</th>
        ${cols.map(c => `<th class="c">${esc(t('rt_month_n', {n: c.month}))}<div class="meta">${esc(`${fmtDate(cal(c.month).from).slice(0, 6)}–${fmtDate(cal(c.month).to).slice(0, 6)}`)}${c.running ? ` · ${esc(t('mv_running'))}` : ''}</div></th>`).join('')}
        <th class="c">Δ${step ? `<div class="meta">${esc(t('mv_pair', {a: step.from_month, b: step.to_month}))}</div>` : ''}</th></tr></thead>
        <tbody>${rows.join('')}</tbody></table></div>
      <p class="meta">${esc(t('mh_hint', {band: fmtNum(months.rules.trend_band)}))}</p></section>`;
  }

  function drawHistoryChart() {
    const host2 = $('#mh-chart');
    const points = months.history.filter(c => c.total != null).map(c => ({value: c.total, short: t('rt_month_n', {n: c.month}),
      label: t('rt_month_n', {n: c.month}) + (c.running ? ` (${t('mv_running')})` : ''), valueText: fmtNum(c.total)}));
    if (!host2 || !points.length) return;
    Charts.line(host2, {title: t('mh_chart'), points, height: 200, unit: '',
      table: {head: [t('rt_month'), t('ov_total'), ...data.rules.parts.map(V.partName)],
              rows: months.history.map(c => [t('rt_month_n', {n: c.month}), c.total == null ? '–' : fmtNum(c.total),
                ...data.rules.parts.map(k => (c.parts[k].score == null ? '–' : fmtNum(c.parts[k].score)))])}});
  }

  function render() {
    const r = data.rules, parts = r.parts;
    const url = fmt => `/api/overall/${id}?${V.query(state, {format: fmt})}`;
    const ranks = [data.overall_rank ? fact(t('ov_rank_all'), data.rank) : '', fact(t('ov_rank_dept'), data.department_rank)].join('');
    const missing = data.missing.length ? t('ov_missing', {parts: data.missing.map(V.partName).join(', ')}) : '';
    host.innerHTML = `<div class="card filters no-print">${V.periodFields(state)}</div>
      <div class="card"><div class="pghead"><div><h2>${esc(data.name)}${data.nickname ? ` <span class="mut">(${esc(data.nickname)})</span>` : ''}</h2>
        <span class="badge">${esc(data.candidate_no)}</span> <span class="meta">${esc(V.periodText(data.period))}</span></div>${V.downloads(url)}</div>
        <dl class="facts">${fact(t('f_department'), data.department && data.department.name)}${fact(t('f_abteilung'), data.abteilung)}
          ${fact(t('ov_th_spv'), data.supervisor)}${fact(t('ov_leaders'), data.leaders)}${fact(t('rb_group'), data.groups)}${ranks}</dl></div>
      <div class="stats">${parts.map(k => tile(V.score(data.parts[k].score), `${V.partName(k)} · ${r.weights[k]} %`)).join('')}
        ${tile(V.score(data.total), t('ov_total'), missing)}</div>
      <p class="hint">${esc(t('ov_hint', {weights: V.weightsText(r)}))}</p>
      ${historyHtml()}
      <div class="profile-grid section-gap">
        ${parts.map(k => `<section class="card"><h3>${esc(V.partName(k))} · ${r.weights[k]} %</h3>${V.partDetailHtml(k, data.parts[k], r)}</section>`).join('')}
      </div>
      <section class="card section-gap"><h3>${esc(t(data.all_ratings ? 'cp_ratings' : 'rb_mine_title'))}</h3>${ratingsHtml()}</section>`;
    drawHistoryChart();
    host.querySelector('.filters').addEventListener('change', ev => {
      if (!V.applyPeriod(state, ev.target, host)) return;
      const p = new URLSearchParams({preset: state.preset});
      if (state.preset === 'custom') { const x = V.period(state); p.set('from', x.from); p.set('to', x.to); }
      history.replaceState(null, '', `${location.pathname}?${p}`);
      load();
    });
  }

  App.onRerender(() => data && render());
  load();
})();

/* Month comparison (Monatsvergleich, report.view): every active Azubi with the overall score per program month,
   the change month A -> month B, trend, key figures (cohort average, counts per trend, top improvers, largest
   declines) and a diverging bar chart of the changes. Everything is computed by the server
   (`services/overall_months.py`); filters go to the API, so the key figures follow them. State lives in the URL. */
(() => {
  const {$, esc, t, api, fmtNum} = App;
  const V = OverallView;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const state = {pair: params.get('vergleich') || '', department: params.get('department') || '',
                 supervisor: params.get('spv') || '', trend: params.get('trend') || ''};
  let data = null;
  let sort = {key: 'delta', desc: true};

  function apiQuery() {
    const p = new URLSearchParams();
    if (state.pair) { const [a, b] = state.pair.split('-'); p.set('from_month', a); p.set('to_month', b); }
    if (state.department) p.set('department_id', state.department);
    if (state.supervisor) p.set('supervisor', state.supervisor);
    if (state.trend) p.set('trend', state.trend);
    return p;
  }

  function syncUrl() {
    const p = new URLSearchParams();
    if (state.pair) p.set('vergleich', state.pair);
    if (state.department) p.set('department', state.department);
    if (state.supervisor) p.set('spv', state.supervisor);
    if (state.trend) p.set('trend', state.trend);
    history.replaceState(null, '', `${location.pathname}${p.toString() ? `?${p}` : ''}`);
  }

  async function load() {
    const out = $('#result') || host;
    out.innerHTML = App.loadingHtml();
    syncUrl();
    try {
      data = await api('GET', `/api/overall/months?${apiQuery()}`);
      if (!$('#result')) renderFrame();
      render();
    } catch (err) {
      App.showError(out, err, load);
    }
  }

  const pairLabel = ([a, b]) => t('mv_pair', {a, b});
  const option = (value, label, current) => `<option value="${esc(value)}"${String(value) === current ? ' selected' : ''}>${esc(label)}</option>`;

  function renderFrame() {
    host.innerHTML = `<div class="card filters no-print">
        <label class="meta">${esc(t('mv_compare'))}<select class="input" name="pair"></select></label>
        <label class="meta">${esc(t('f_department'))}<select class="input" name="department"></select></label>
        <label class="meta">${esc(t('ov_th_spv'))}<select class="input" name="supervisor"></select></label>
        <label class="meta">${esc(t('mv_th_trend'))}<select class="input" name="trend"></select></label>
      </div><div id="result" aria-live="polite"></div>`;
    host.querySelector('.filters').addEventListener('change', ev => {
      state[ev.target.name] = ev.target.value;
      load();
    });
    host.querySelector('#result').addEventListener('click', ev => {
      const head = ev.target.closest('[data-sort]');
      if (head) {
        const key = head.dataset.sort;
        sort = sort.key === key ? {key, desc: !sort.desc} : {key, desc: key !== 'name'};
        render();
        return;
      }
      const tile = ev.target.closest('[data-trend]');
      if (tile) {
        state.trend = state.trend === tile.dataset.trend ? '' : tile.dataset.trend;
        load();
      }
    });
  }

  function filterOptions() {
    const pair = data.pair.join('-');
    host.querySelector('[name=pair]').innerHTML = (data.pairs.length ? data.pairs : [data.pair]).map(p => option(p.join('-'), pairLabel(p), pair)).join('');
    host.querySelector('[name=department]').innerHTML = option('', t('ov_all_departments'), state.department)
      + data.departments.map(d => option(d.id, d.name, state.department)).join('');
    host.querySelector('[name=supervisor]').innerHTML = option('', t('mv_supervisor_all'), state.supervisor)
      + data.supervisors.map(s => option(s, s, state.supervisor)).join('');
    host.querySelector('[name=trend]').innerHTML = option('', t('mv_trend_all'), state.trend)
      + data.rules.trends.map(x => option(x, t('mv_trend_' + x), state.trend)).join('');
  }

  /* ---------- key figures ---------- */

  function nameList(list, empty) {
    if (!list.length) return `<span class="meta">${esc(empty)}</span>`;
    return `<ol class="mv-names">${list.map(x => `<li><a href="/overall/${x.id}">${esc(x.name)}</a>
      <b>${esc(V.signed(x.delta))}</b></li>`).join('')}</ol>`;
  }

  function kpisHtml() {
    const s = data.summary, [a, b] = data.pair, c = s.cohort;
    const trendTile = trend => `<button type="button" class="stat mv-tile${state.trend === trend ? ' on' : ''}" data-trend="${trend}"
      aria-pressed="${state.trend === trend}"><b>${s.counts[trend]}</b><span>${V.trendBadge(trend)}</span></button>`;
    return `<div class="stats mv-kpis">
      <div class="stat"><b class="small">${esc(c.from == null ? '–' : `${fmtNum(c.from)} → ${fmtNum(c.to)}`)}</b>
        <span>${esc(t('mv_kpi_cohort', {a, b}))}</span>
        <small class="meta">${esc(c.delta == null ? t('mv_chart_empty') : t('mv_kpi_cohort_sub', {delta: V.signed(c.delta), n: s.comparable}))}</small></div>
      ${['IMPROVED', 'STAGNANT', 'DECLINED'].map(trendTile).join('')}
      <div class="stat mv-list"><span>${esc(t('mv_kpi_top'))}</span>${nameList(s.top_improvers, t('mv_kpi_none'))}</div>
      <div class="stat mv-list"><span>${esc(t('mv_kpi_attention'))}</span>${nameList(s.top_decliners, t('mv_kpi_none'))}</div>
    </div>`;
  }

  /* ---------- diverging bar chart: change per Azubi ---------- */

  function chartHtml() {
    const rows = data.rows.filter(r => r.compare.delta != null).sort((x, y) => y.compare.delta - x.compare.delta);
    const [a, b] = data.pair;
    if (!rows.length) return `<section class="card"><h3>${esc(t('mv_chart_title', {a, b}))}</h3>${App.emptyHtml(t('mv_chart_empty'))}</section>`;
    const max = Math.max(data.rules.trend_band * 2, ...rows.map(r => Math.abs(r.compare.delta)));
    const bar = r => {
      const d = r.compare.delta, w = Math.abs(d) / max * 50;
      const cls = r.compare.trend === 'IMPROVED' ? 'up' : r.compare.trend === 'DECLINED' ? 'down' : 'flat';
      const tip = t('mv_bar_tip', {name: r.name, from: fmtNum(r.compare.from), to: fmtNum(r.compare.to), delta: V.signed(d)});
      return `<li title="${esc(tip)}"><a class="mv-bar-name" href="/overall/${r.id}">${esc(r.name)}</a>
        <span class="mv-track"><i class="mv-bar ${cls}" style="${d < 0 ? 'right' : 'left'}:50%;width:${w.toFixed(2)}%"></i></span>
        <b class="mv-bar-val">${esc(V.signed(d))}</b></li>`;
    };
    return `<section class="card"><h3>${esc(t('mv_chart_title', {a, b}))}</h3>
      <p class="meta">${esc(t('mv_chart_hint', {band: fmtNum(data.rules.trend_band)}))}</p>
      <ul class="mv-bars" role="list">${rows.map(bar).join('')}</ul></section>`;
  }

  /* ---------- table ---------- */

  function sortValue(r) {
    if (sort.key === 'name') return r.name.toLowerCase();
    if (sort.key === 'total') return r.total;
    if (sort.key === 'delta') return r.compare.delta;
    if (sort.key === 'percent') return r.compare.percent;
    const m = r.months[sort.key];
    return m ? m.total : null;
  }

  function sortedRows() {
    return [...data.rows].sort((x, y) => {
      const a = sortValue(x), b = sortValue(y);
      if (a == null) return b == null ? 0 : 1;          // pending/not comparable always at the bottom
      if (b == null) return -1;
      const cmp = typeof a === 'string' ? a.localeCompare(b) : a - b;
      return sort.desc ? -cmp : cmp;
    });
  }

  function monthCell(m) {
    if (!m) return '–';
    return `${V.score(m.total)}${m.running ? `<div class="meta">${esc(t('mv_running'))}</div>` : ''}`;
  }

  function deltaCell(c) {
    if (c.delta == null) return '–';
    const partial = c.parts.length < data.rules.parts.length
      ? `<div class="meta">${esc(t('mv_compared_values', {from: fmtNum(c.from), to: fmtNum(c.to),
        parts: c.parts.map(V.partName).join(', ')}))}</div>` : '';
    return `<b class="mv-delta">${esc(V.signed(c.delta))}</b>${partial}`;
  }

  function tableHtml() {
    const months = data.started.map(String);
    const arrow = key => (sort.key === key ? (sort.desc ? ' ▼' : ' ▲') : '');
    const th = (key, label, sub, cls = 'c') => `<th class="${cls}"><button class="sort" type="button" data-sort="${esc(key)}">${esc(label)}${arrow(key)}${sub ? `<div class="meta">${esc(sub)}</div>` : ''}</button></th>`;
    const cal = m => data.calendar[Number(m) - 1];
    if (!data.rows.length) return `<section class="card">${App.emptyHtml(t('mv_empty'))}</section>`;
    return `<section class="card"><div class="tbl-wrap"><table class="tbl mv-table"><thead><tr>
      <th class="c">${esc(t('th_rank'))}</th>${th('name', t('f_name'), '', '')}<th>${esc(t('f_department'))}</th><th>${esc(t('ov_th_spv'))}</th>
      ${months.map(m => th(m, t('rt_month_n', {n: m}), `${App.fmtDate(cal(m).from).slice(0, 6)}–${App.fmtDate(cal(m).to).slice(0, 6)}`)).join('')}
      ${th('delta', t('mv_th_delta'), pairLabel(data.pair))}${th('percent', t('mv_th_percent'))}
      ${th('total', t('ov_total'), t('mv_whole_program'))}<th>${esc(t('mv_th_trend'))}</th></tr></thead>
      <tbody>${sortedRows().map(r => `<tr>
        <td class="c">${r.rank ?? '–'}</td>
        <td class="name"><a href="/overall/${r.id}">${esc(r.name)}</a>${r.nickname ? ` <span class="mut">(${esc(r.nickname)})</span>` : ''}</td>
        <td>${esc(r.department ? r.department.name : '–')}</td><td class="nw">${esc(r.supervisor || '–')}</td>
        ${months.map(m => `<td class="c">${monthCell(r.months[m])}</td>`).join('')}
        <td class="c">${deltaCell(r.compare)}</td>
        <td class="c nw">${r.compare.percent == null ? '–' : esc(`${V.signed(r.compare.percent)} %`)}</td>
        <td class="c">${V.score(r.total)}</td><td>${V.trendBadge(r.compare.trend)}</td></tr>`).join('')}
      </tbody></table></div></section>`;
  }

  function render() {
    filterOptions();
    const [a, b] = data.pair;
    $('#result').innerHTML = `<p class="hint">${esc(t('mv_hint', {a, b, band: fmtNum(data.rules.trend_band)}))}</p>
      ${kpisHtml()}${chartHtml()}${tableHtml()}`;
  }

  App.onRerender(() => { if (data) { renderFrame(); render(); } });
  load();
})();

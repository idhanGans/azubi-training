/* Rating page (Bewerten): SPV (own Azubis), leader (whole department) and internal team (all active ones) rate
   practical performance, reliability and motivation & behaviour (1–10), once per program month. Which Azubis and
   as what is decided by the server (`kind`), the months too (`month` = running one, `calendar` = dates per month).
   The month tabs switch the whole list to one month (values, status, "Bewerten" for exactly that month);
   "Alle Monate" shows every month side by side. From other raters only count + average; own ratings in full,
   correctable on the day of submission. */
(() => {
  const {$, esc, t, api, fmtDate, fmtDateTime, fmtNum, toast} = App;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const state = {q: '', group: '', open: false, month: params.get('monat')};
  const cat = c => OverallView.categoryName(c);
  let data = null;

  const byId = id => data.trainees.find(x => x.id === id);
  const displayName = x => x.nickname ? `${x.name} (${x.nickname})` : x.name;
  const avg = v => (v == null ? '–' : fmtNum(v));
  const range = c => `${fmtDate(c.from)} – ${fmtDate(c.to)}`;
  const started = () => data.calendar.filter(c => c.started);
  const scores = r => data.categories.map(c => avg(r[c])).join(' · ');
  const monthStats = (x, m) => (x.stats.months || {})[m] || null;

  async function load() {
    if (!data) host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', '/api/rating-board');
      const valid = state.month === 'all' || data.months.includes(Number(state.month));
      state.month = !valid ? data.month : state.month === 'all' ? 'all' : Number(state.month);
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function groups() {
    return [...new Set(data.trainees.flatMap(x => x.groups))].sort();
  }

  function isOpen(x) {
    return state.month === 'all' ? data.months.some(m => !x.mine[m]) : !x.mine[state.month];
  }

  function visible() {
    const q = state.q.trim().toLowerCase();
    return data.trainees.filter(x => (!q || `${x.name} ${x.nickname || ''}`.toLowerCase().includes(q))
      && (!state.group || x.groups.includes(state.group)) && (!state.open || isOpen(x)));
  }

  function num(label, value, title) {
    return `<span${title ? ` title="${esc(title)}"` : ''}><small>${esc(label)}</small><b>${esc(value)}</b></span>`;
  }

  const where = x => {
    const dept = x.department && x.department.name;
    return [dept, x.abteilung !== dept && x.abteilung, x.groups.join(', ')].filter(Boolean).join(' · ') || '–';
  };

  const statusBadge = (x, m) => (x.mine[m]
    ? `<span class="badge ok">${esc(t('rb_month_done', {n: m}))}</span>`
    : `<span class="badge warn">${esc(t('rb_month_open', {n: m}))}</span>`);

  const rateBtn = (x, m) => `<button class="btn sm" type="button" data-action="rate" data-id="${x.id}"
    data-month="${m}">${esc(t('btn_rate'))}</button>`;
  const correctBtn = (x, m) => `<button class="btn ghost sm" type="button" data-action="correct" data-id="${x.id}"
    data-month="${m}">${esc(t('btn_correct'))}</button>`;

  function monthTabs() {
    const total = data.trainees.length;
    const tab = (key, label, lines, disabled) => `<button type="button" role="tab" data-month="${key}"
      aria-selected="${state.month === key}"${disabled ? ' disabled' : ''}><span>${esc(label)}</span>
      ${lines.map(l => `<small>${esc(l)}</small>`).join('')}</button>`;
    return `<div class="tabs rb-months no-print" role="tablist" aria-label="${esc(t('rt_month'))}">
      ${data.calendar.map(c => tab(c.month, t('rt_month_n', {n: c.month}) + (c.month === data.month ? ` · ${t('rb_month_running')}` : ''),
        [range(c), c.started ? t('rb_month_progress', {done: data.trainees.filter(x => x.mine[c.month]).length, total})
          : t('rb_month_from', {date: fmtDate(c.from)})], !c.started)).join('')}
      ${tab('all', t('rb_all_months'), [t('rb_all_months_sub')], false)}</div>`;
  }

  function rowHtml(x) {
    const m = state.month;
    const s = monthStats(x, m) || {count: 0};
    const own = x.mine[m];
    return `<li class="rb-item">
      <div class="rb-who"><b>${esc(x.name)}${x.nickname ? ` <span class="mut">(${esc(x.nickname)})</span>` : ''}</b>
        <span class="meta">${esc(where(x))}</span>
        <span><span class="badge">${esc(t('rb_as', {kind: OverallView.kindName(x.kind)}))}</span> ${statusBadge(x, m)}</span></div>
      <div class="rb-nums">${num(t('rb_count'), String(s.count))}
        ${data.categories.map(c => num(t('rb_avg', {name: cat(c)}), avg(s[c]))).join('')}
        ${num(t('rb_mine_month'), own ? scores(own) : '–', data.categories.map(cat).join(' · '))}
        ${s.last ? num(t('rb_last'), fmtDateTime(s.last)) : ''}</div>
      <div class="row-actions">
        ${own ? (own.editable ? correctBtn(x, m) : '') : rateBtn(x, m)}
        <button class="btn ghost sm" type="button" data-action="details" data-id="${x.id}">${esc(t('rb_details'))}</button>
      </div></li>`;
  }

  function cellHtml(x, c) {
    if (!c.started) return `<span class="mut">${esc(t('rb_month_from', {date: fmtDate(c.from)}))}</span>`;
    const own = x.mine[c.month];
    const s = monthStats(x, c.month);
    const others = s ? `<small class="meta">${esc(t('rb_others_month', {avg: avg(s.mean), n: s.count}))}</small>` : '';
    if (!own) return `<div class="rb-cell">${rateBtn(x, c.month)}${others}</div>`;
    return `<div class="rb-cell"><b title="${esc(data.categories.map(cat).join(' · '))}">${esc(scores(own))}</b>${others}
      ${own.editable ? correctBtn(x, c.month) : ''}</div>`;
  }

  function gridHtml(rows) {
    return `<div class="tbl-wrap"><table class="tbl rb-grid"><thead><tr><th>${esc(t('as_candidate'))}</th>
      ${data.calendar.map(c => `<th><button type="button" class="rb-colhead" data-month="${c.month}"${c.started ? '' : ' disabled'}>${esc(t('rt_month_n', {n: c.month}))}</button>
        <small class="meta">${esc(range(c))}</small></th>`).join('')}<th>${esc(t('th_actions'))}</th></tr></thead><tbody>
      ${rows.map(x => `<tr><td><b>${esc(x.name)}</b>${x.nickname ? ` <span class="mut">(${esc(x.nickname)})</span>` : ''}
          <small class="meta">${esc(where(x))}</small></td>
        ${data.calendar.map(c => `<td>${cellHtml(x, c)}</td>`).join('')}
        <td><button class="btn ghost sm" type="button" data-action="details" data-id="${x.id}">${esc(t('rb_details'))}</button></td></tr>`).join('')}
      </tbody></table></div>
      <p class="meta">${esc(t('rb_grid_hint', {cats: data.categories.map(cat).join(' · ')}))}</p>`;
  }

  function resultsHtml() {
    if (!data.trainees.length) return App.emptyHtml(t(data.internal ? 'rb_empty' : 'rb_empty_assigned'));
    const rows = visible();
    if (!rows.length) return App.emptyHtml(t('rb_no_match'));
    return `<p class="meta">${esc(t('tm_count', {n: rows.length}))}</p>`
      + (state.month === 'all' ? gridHtml(rows) : `<ul class="rb-list">${rows.map(rowHtml).join('')}</ul>`);
  }

  function monthHint() {
    if (state.month === 'all') return t('rb_all_hint', {n: data.month, max: data.program_months});
    const c = data.calendar[state.month - 1];
    return t('rb_month_now', {n: state.month, max: data.program_months, range: range(c)});
  }

  function render() {
    const current = groups();
    if (state.group && !current.includes(state.group)) state.group = '';
    const onlyOpen = state.month === 'all' ? t('rb_only_open_any') : t('rb_only_open_month', {n: state.month});
    host.innerHTML = `<div class="card">
      <p class="hint">${esc(t(data.internal ? 'rb_hint_internal' : 'rb_hint', {min: data.scale[0], max: data.scale[1]}))}</p>
      ${monthTabs()}
      <p class="hint">${esc(monthHint())}</p>
      <form class="filters" role="search">
        <input class="input" type="search" name="q" value="${esc(state.q)}" placeholder="${esc(t('rb_search_ph'))}" aria-label="${esc(t('cl_search'))}">
        <select class="input" name="group" aria-label="${esc(t('rb_group'))}"><option value="">${esc(t('rb_all_groups'))}</option>
          ${current.map(g => `<option value="${esc(g)}"${g === state.group ? ' selected' : ''}>${esc(g)}</option>`).join('')}</select>
        <span class="checks"><label><input type="checkbox" name="open"${state.open ? ' checked' : ''}> ${esc(onlyOpen)}</label></span>
      </form>
      <div id="results" aria-live="polite">${resultsHtml()}</div>
    </div>`;
    const form = host.querySelector('form');
    form.addEventListener('submit', ev => ev.preventDefault());
    form.addEventListener('input', () => {
      state.q = form.q.value;
      state.group = form.group.value;
      state.open = form.open.checked;
      $('#results').innerHTML = resultsHtml();
    });
  }

  function switchMonth(key) {
    state.month = key === 'all' ? 'all' : Number(key);
    const url = new URL(location.href);
    url.searchParams.set('monat', String(state.month));
    history.replaceState(null, '', url);
    render();
  }

  function rate(x, month, existing) {
    const [min, max] = data.scale;
    const c = data.calendar[month - 1];
    const num = name => ({name, label: cat(name), type: 'number', min, max, step: 1, required: true,
                          value: existing ? existing[name] ?? '' : ''});
    App.formDialog({
      title: t(existing ? 'dlg_rate_edit' : 'dlg_rate', {name: `${displayName(x)} · ${t('rt_month_n', {n: month})}`}),
      intro: `${t('rb_rate_month_hint', {n: month, range: range(c)})} ${t('rate_hint', {min, max, kind: OverallView.kindName(x.kind)})}`,
      fields: [...data.categories.map(num),
        {name: 'note', label: t('f_note'), type: 'textarea', maxlength: 1000, value: existing ? existing.note || '' : ''}],
      onSubmit: async v => {
        if (existing) await api('PATCH', `/api/ratings/${existing.id}`, v);
        else await api('POST', '/api/ratings', {...v, month, trainee_id: x.id});
        toast(t('saved'));
        await load();
      },
    });
  }

  function perMonthHtml(s) {
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('rt_month'))}</th><th class="c">${esc(t('rb_count'))}</th>
      ${data.categories.map(c => `<th class="c">${esc(t('rb_avg', {name: cat(c)}))}</th>`).join('')}<th class="c">${esc(t('rb_mean'))}</th></tr></thead><tbody>
      ${started().map(c => { const m = monthStats(s, c.month) || {count: 0};
        return `<tr><td class="nw">${esc(t('rt_month_n', {n: c.month}))}</td><td class="c">${m.count}</td>
          ${data.categories.map(k => `<td class="c">${esc(avg(m[k]))}</td>`).join('')}<td class="c">${esc(avg(m.mean))}</td></tr>`; }).join('')}
      </tbody></table></div>`;
  }

  function mineHtml(x) {
    return `<div class="tbl-wrap"><table class="tbl rb-mine"><thead><tr><th>${esc(t('rt_month'))}</th><th>${esc(t('th_date'))}</th>
      ${data.categories.map(c => `<th class="c">${esc(cat(c))}</th>`).join('')}
      <th>${esc(t('f_note'))}</th><th>${esc(t('th_actions'))}</th></tr></thead><tbody>
      ${started().map(c => { const r = x.mine[c.month];
        if (!r) {
          return `<tr><td class="nw">${esc(t('rt_month_n', {n: c.month}))}</td>
            <td colspan="${data.categories.length + 2}"><span class="badge warn">${esc(t('rb_not_rated'))}</span></td>
            <td>${rateBtn(x, c.month)}</td></tr>`;
        }
        return `<tr><td class="nw">${esc(t('rt_month_n', {n: c.month}))}</td>
          <td class="nw">${esc(fmtDateTime(r.created_at))}${r.updated_at ? ` <span class="mut">${esc(t('rb_corrected'))}</span>` : ''}</td>
          ${data.categories.map(k => `<td class="c">${esc(avg(r[k]))}</td>`).join('')}
          <td class="wrap">${esc(r.note || '–')}</td>
          <td>${r.editable ? correctBtn(x, c.month) : ''}</td></tr>`; }).join('')}
      </tbody></table></div>`;
  }

  async function details(x) {
    const dlg = App.openDialog(t('rb_details_title', {name: displayName(x)}), App.loadingHtml());
    const body = dlg.querySelector('.dlg-body');
    try {
      const d = await api('GET', `/api/rating-board/${x.id}`);
      const s = d.trainee;
      body.innerHTML = `<p class="meta">${esc(where(s))} · ${esc(t('rb_as', {kind: OverallView.kindName(s.kind)}))}</p>
        <p>${esc(t('rb_summary', {n: s.stats.count, part: OverallView.partName(s.part)}))}
          ${d.categories.map(c => `${esc(cat(c))}: <b>${esc(avg(s.stats[c]))}</b>`).join(' · ')}</p>
        <h4 class="form-section">${esc(t('rb_by_month'))}</h4>${perMonthHtml(s)}
        <p class="hint">${esc(t('rb_others_hint'))}</p>
        <h4 class="form-section">${esc(t('rb_mine_title'))}</h4>${mineHtml(s)}`;
      App.onActions(body, {
        rate: (id, el) => { dlg.close(); rate(s, Number(el.dataset.month)); },
        correct: (id, el) => { dlg.close(); rate(s, Number(el.dataset.month), s.mine[el.dataset.month]); },
      });
    } catch (err) {
      body.innerHTML = `<div class="state error" role="alert">${esc(err.message)}</div>`;
    }
  }

  host.addEventListener('click', ev => {
    const tab = ev.target.closest('[data-month]:not([data-action])');
    if (tab && !tab.disabled) switchMonth(tab.dataset.month);
  });
  App.onActions(host, {
    rate: (id, el) => rate(byId(id), Number(el.dataset.month)),
    correct: (id, el) => rate(byId(id), Number(el.dataset.month), byId(id).mine[el.dataset.month]),
    details: id => details(byId(id)),
  });
  App.onRerender(() => data && render());
  load();
})();

/* Overall rating: ranking (overall and per department) from report, German, SPV and internal — Excel/PDF download.
   Without report.view only the trainees assigned as SPV/leader (filtered by the server). State lives in the URL. */
(() => {
  const {$, esc, t, api, toast} = App;
  const V = OverallView;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const state = {...V.readState(params), department: params.get('department') || ''};
  let data = null;
  let sort = null;   // {key: 'report'|'german'|'spv'|'intern'|'total', desc} — null = server order (rank)
  const expanded = new Set();   // expanded part aspects, key `${traineeId}:${partKey}`

  /* Sort rows by the clicked column; "Ausstehend" (pending, null) always stays at the bottom. */
  function sortedRows() {
    const rows = [...data.rows];
    if (!sort) return rows;
    const val = r => (sort.key === 'total' ? r.total : r.parts[sort.key].score);
    rows.sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null) return 1;
      if (y == null) return -1;
      return sort.desc ? y - x : x - y;
    });
    return rows;
  }

  function apiQuery(extra) {
    const p = V.query(state, extra);
    if (state.department) p.set('department_id', state.department);
    return p;
  }

  function syncUrl() {
    const p = new URLSearchParams({preset: state.preset});
    if (state.department) p.set('department', state.department);
    if (state.preset === 'custom') { const x = V.period(state); p.set('from', x.from); p.set('to', x.to); }
    history.replaceState(null, '', `${location.pathname}?${p}`);
  }

  async function load() {
    const out = $('#result') || host;
    out.innerHTML = App.loadingHtml();
    syncUrl();
    try {
      data = await api('GET', `/api/overall?${apiQuery()}`);
      if (!$('#result')) renderFrame();
      render();
    } catch (err) {
      App.showError(out, err, load);
    }
  }

  function renderFrame() {
    host.innerHTML = `<div class="card filters no-print">
        <label class="meta">${esc(t('f_department'))}<select class="input" name="department"></select></label>
        ${V.periodFields(state)}
      </div><div id="result" aria-live="polite"></div>`;
    host.querySelector('.filters').addEventListener('change', ev => {
      if (ev.target.name === 'department') state.department = ev.target.value;
      else if (!V.applyPeriod(state, ev.target, host)) return;
      load();
    });
    host.querySelector('#result').addEventListener('click', ev => {
      const head = ev.target.closest('[data-sort]');
      if (head) {
        const key = head.dataset.sort;
        sort = sort && sort.key === key ? {key, desc: !sort.desc} : {key, desc: true};
        render();
        return;
      }
      const cell = ev.target.closest('[data-detail]');     // click part score -> expand/collapse aspects
      if (!cell) return;
      const key = cell.dataset.detail;
      if (expanded.has(key)) expanded.delete(key); else expanded.add(key);
      render();
    });
    host.querySelector('#result').addEventListener('change', ev => {   // save note when leaving the field
      const ta = ev.target.closest('[data-note]');
      if (ta) saveNote(ta);
    });
  }

  function departmentOptions() {
    const sel = host.querySelector('[name=department]');
    const known = data.departments.some(d => String(d.id) === state.department);
    sel.innerHTML = `<option value="">${esc(t('ov_all_departments'))}</option>` + data.departments.map(d =>
      `<option value="${d.id}"${String(d.id) === state.department ? ' selected' : ''}>${esc(d.name)}</option>`).join('')
      + (state.department && !known ? `<option value="${esc(state.department)}" selected>–</option>` : '');
  }

  /* fixed 2-week checkpoints from the server; header label 2026-10-19 -> "19.10." */
  const checkpoints = () => data.note_checkpoints || [];
  const cpLabel = iso => `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;

  function noteCell(r, cp) {
    const text = (r.notes && r.notes[cp]) || '';
    if (!data.can_edit_notes) return `<div class="noteview">${esc(text) || '–'}</div>`;
    return `<textarea class="noteedit" rows="2" data-note="${r.id}:${esc(cp)}" placeholder="${esc(t('ov_note_ph'))}">${esc(text)}</textarea>`;
  }

  /* Save note live (when leaving the field); empty text deletes it. */
  async function saveNote(ta) {
    const [idStr, cp] = ta.dataset.note.split(':');
    const id = Number(idStr);
    ta.classList.remove('failed');
    try {
      const res = await api('PUT', '/api/overall/notes', {trainee_id: id, checkpoint: cp, text: ta.value});
      const row = data.rows.find(r => r.id === id);
      if (row) { row.notes = row.notes || {}; if (res.text) row.notes[cp] = res.text; else delete row.notes[cp]; }
      ta.value = res.text || '';
      ta.classList.add('saved');
      setTimeout(() => ta.classList.remove('saved'), 1500);
      toast(t('ov_note_saved'));
    } catch (err) {
      ta.classList.add('failed');
      toast(err.message, 'error');
    }
  }

  function rowHtml(r, parts) {
    const span = (data.overall_rank ? 1 : 0) + 5 + parts.length + checkpoints().length;
    const main = `<tr>
      ${data.overall_rank ? `<td class="c">${r.rank ?? '–'}</td>` : ''}<td class="c">${r.department_rank ?? '–'}</td>
      <td class="name"><a href="/overall/${r.id}${location.search}">${esc(r.name)}</a>${r.nickname ? ` <span class="mut">(${esc(r.nickname)})</span>` : ''}
        <div class="meta">${esc(r.abteilung || '')}</div></td>
      <td>${esc(r.department ? r.department.name : '–')}</td><td class="nw">${esc(r.supervisor || '–')}</td>
      ${parts.map(k => `<td class="c"><button class="cellbtn" type="button" data-detail="${r.id}:${esc(k)}" aria-expanded="${expanded.has(`${r.id}:${k}`)}">${V.score(r.parts[k].score)}</button></td>`).join('')}
      <td class="c">${V.score(r.total)}</td>
      ${checkpoints().map(cp => `<td class="note">${noteCell(r, cp)}</td>`).join('')}</tr>`;
    const detail = parts.filter(k => expanded.has(`${r.id}:${k}`)).map(k =>
      `<tr class="detrow"><td class="aspect" colspan="${span}"><strong>${esc(V.partName(k))} · ${data.rules.weights[k]} %</strong>${V.partDetailHtml(k, r.parts[k], data.rules)}</td></tr>`).join('');
    return main + detail;
  }

  function render() {
    departmentOptions();
    const out = $('#result');
    const parts = data.rules.parts;
    const url = fmt => `/api/overall?${apiQuery({format: fmt})}`;
    const complete = data.rows.filter(r => !r.missing.length).length;
    const empty = can => App.emptyHtml(t(can ? 'ov_empty' : 'ov_empty_assigned'));
    const arrow = key => (sort && sort.key === key ? (sort.desc ? ' ▼' : ' ▲') : '');
    const sortTh = (key, label, sub) => `<th class="c"><button class="sort" type="button" data-sort="${esc(key)}">${esc(label)}${arrow(key)}${sub ? `<div class="meta">${esc(sub)}</div>` : ''}</button></th>`;
    out.innerHTML = `<div class="card">
      <div class="pghead"><span class="meta">${esc(t('ov_count', {n: data.rows.length, c: complete}))} · ${esc(V.periodText(data.period))}</span>
        ${App.can('report.view') ? `<a class="btn ghost sm no-print" href="/overall/months">${App.icon('trending')} ${esc(t('nav_overall_months'))}</a>` : ''}
        ${data.rows.length ? V.downloads(url) : ''}</div>
      <p class="hint">${esc(t('ov_hint', {weights: V.weightsText(data.rules)}))}</p>
      ${data.rows.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>
        ${data.overall_rank ? `<th class="c">${esc(t('th_rank'))}</th>` : ''}<th class="c">${esc(t('ov_th_dept_rank'))}</th>
        <th>${esc(t('f_name'))}</th><th>${esc(t('f_department'))}</th><th>${esc(t('ov_th_spv'))}</th>
        ${parts.map(k => sortTh(k, V.partName(k), `${data.rules.weights[k]} %`)).join('')}
        ${sortTh('total', t('ov_total'))}
        ${checkpoints().map(cp => `<th class="c note" title="${esc(t('ov_notes'))}">${esc(cpLabel(cp))}</th>`).join('')}</tr></thead>
        <tbody>${sortedRows().map(r => rowHtml(r, parts)).join('')}</tbody></table></div>` : empty(App.can('report.view'))}
    </div>`;
  }

  App.onRerender(() => { if (data) { renderFrame(); render(); } });
  load();
})();

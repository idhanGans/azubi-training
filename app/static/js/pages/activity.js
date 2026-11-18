/* Verlauf: Audit-Trail aller Aenderungen (neueste zuerst, unveraenderlich) mit Filtern und „Mehr laden". */
(() => {
  const {$, esc, t, api} = App;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const state = {actor: params.get('actor') || '', action: params.get('action') || '', entity_type: params.get('entity_type') || '',
                 from: params.get('from') || '', to: params.get('to') || '', q: params.get('q') || ''};
  let facets = null, entries = [], next = null;

  function query(before) {
    const p = new URLSearchParams();
    Object.entries(state).forEach(([k, v]) => { if (v) p.set(k, v); });
    if (before) p.set('before_id', before);
    return p.toString();
  }

  async function init() {
    host.innerHTML = App.loadingHtml();
    try {
      facets = await api('GET', '/api/activity/facets');
      renderFrame();
      await load();
    } catch (err) {
      App.showError(host, err, init);
    }
  }

  /* Aktions-Gruppe (Praefix vor dem Punkt): „session" -> „Termine" */
  const groupLabel = g => (I18N['vl_group_' + g] ? t('vl_group_' + g) : g);

  function renderFrame() {
    const opt = (v, label, cur) => `<option value="${esc(v)}"${v === cur ? ' selected' : ''}>${esc(label)}</option>`;
    const groups = [...new Set(facets.actions.map(a => a.split('.')[0]))];
    host.innerHTML = `<p class="hint">${esc(t('vl_hint_protected'))}</p>
      <div class="card filters">
        <label class="meta">${esc(t('vl_actor'))}<select class="input" name="actor">${opt('', t('vl_all'), state.actor)}
          ${facets.actors.map(a => opt(a.login, a.name ? `${a.name} (${a.login})` : a.login, state.actor)).join('')}</select></label>
        <label class="meta">${esc(t('vl_action'))}<select class="input" name="action">${opt('', t('vl_all'), state.action)}
          ${groups.map(g => `<optgroup label="${esc(groupLabel(g))}">${opt(g, t('vl_all_of', {x: groupLabel(g)}), state.action)}
            ${facets.actions.filter(a => a.split('.')[0] === g).map(a => opt(a, ActivityList.actionLabel(a), state.action)).join('')}</optgroup>`).join('')}</select></label>
        <label class="meta">${esc(t('vl_entity'))}<select class="input" name="entity_type">${opt('', t('vl_all'), state.entity_type)}
          ${facets.entity_types.map(e => opt(e, ActivityList.entityLabel(e), state.entity_type)).join('')}</select></label>
        <label class="meta">${esc(t('rp_from'))}<input class="input" type="date" name="from" value="${esc(state.from)}"></label>
        <label class="meta">${esc(t('rp_to'))}<input class="input" type="date" name="to" value="${esc(state.to)}"></label>
        <label class="meta">${esc(t('vl_search'))}<input class="input" type="search" name="q" value="${esc(state.q)}" placeholder="${esc(t('vl_search_ph'))}"></label>
      </div><div class="card" id="results"></div>`;
  }

  async function load(more) {
    const results = $('#results');
    if (!more) { results.innerHTML = App.loadingHtml(); entries = []; }
    history.replaceState(null, '', location.pathname + (query() ? `?${query()}` : ''));
    try {
      const body = await api('GET', `/api/activity?${query(more ? next : null)}`);
      entries = entries.concat(body.activity);
      next = body.next_before_id;
      results.innerHTML = entries.length ? `<p class="meta">${esc(t('vl_count', {n: entries.length}))}</p>${ActivityList.tableHtml(entries)}
        ${next ? `<button class="btn ghost sm" type="button" data-more>${esc(t('vl_more'))}</button>` : ''}` : App.emptyHtml(t('vl_empty'));
    } catch (err) {
      App.showError(results, err, () => load(more));
    }
  }

  let timer = null;
  host.addEventListener('change', ev => {
    if (!(ev.target.name in state) || ev.target.name === 'q') return;
    state[ev.target.name] = ev.target.value;
    load();
  });
  host.addEventListener('input', ev => {
    if (ev.target.name !== 'q') return;
    clearTimeout(timer);
    timer = setTimeout(() => { state.q = ev.target.value.trim(); load(); }, 300);
  });
  host.addEventListener('click', ev => { if (ev.target.closest('[data-more]')) load(true); });
  App.onRerender(() => { if (facets) { renderFrame(); load(); } });
  init();
})();

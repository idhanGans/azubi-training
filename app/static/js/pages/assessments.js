/* Bewertungen: Liste mit Filtern (Status, Vorlage, nur meine), neue Bewertung, Link zu den Vorlagen. */
(() => {
  const {$, esc, t, can, api} = App;
  const host = $('#page');
  const params = new URLSearchParams(location.search);
  const state = {status: params.get('status') || '', template_id: params.get('template_id') || '', mine: params.get('mine') === '1',
                 page: Math.max(1, parseInt(params.get('page'), 10) || 1)};
  let templates = [];
  let list = null;        // {assessments, total, page, per_page}

  function query() {
    const p = new URLSearchParams();
    if (state.status) p.set('status', state.status);
    if (state.template_id) p.set('template_id', state.template_id);
    if (state.mine) p.set('mine', '1');
    if (state.page > 1) p.set('page', String(state.page));
    return p.toString();
  }

  async function load() {
    const results = $('#results');
    if (results) results.innerHTML = App.loadingHtml();
    else host.innerHTML = App.loadingHtml();              // erster Aufruf: noch keine Filterleiste
    try {
      const [body, tp] = await Promise.all([api('GET', `/api/assessments?${query()}`),
                                            templates.length ? {templates} : api('GET', '/api/assessment-templates')]);
      list = body;
      templates = tp.templates;
      history.replaceState(null, '', location.pathname + (query() ? '?' + query() : ''));
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function pagerHtml() {
    const pages = Math.max(1, Math.ceil(list.total / list.per_page));
    if (pages <= 1) return '';
    const label = t('cl_page', {p: list.page, n: pages});
    return `<nav class="pager" aria-label="${esc(label)}">
      <button class="btn ghost sm" type="button" data-action="page" data-id="${list.page - 1}"${list.page <= 1 ? ' disabled' : ''}>${esc(t('cl_prev'))}</button>
      <span class="meta">${esc(label)}</span>
      <button class="btn ghost sm" type="button" data-action="page" data-id="${list.page + 1}"${list.page >= pages ? ' disabled' : ''}>${esc(t('cl_next'))}</button></nav>`;
  }

  function render() {
    const opt = (v, l, cur) => `<option value="${esc(v)}"${String(v) === String(cur) ? ' selected' : ''}>${esc(l)}</option>`;
    host.innerHTML = `<div class="pghead"><p class="hint inline">${esc(t('as_list_hint'))}</p><div class="tools">
        <a class="btn ghost sm" href="/assessment-templates">${esc(t('page_assessment_templates'))}</a>
        ${can('assessment.create') ? `<button class="btn sm" type="button" data-action="add">${esc(t('as_new'))}</button>` : ''}</div></div>
      <div class="card"><div class="filters">
        <select name="status" class="input" aria-label="${esc(t('f_status'))}">${opt('', t('as_all_status'), state.status)}
          ${opt('DRAFT', t('as_DRAFT'), state.status)}${opt('FINAL', t('as_FINAL'), state.status)}</select>
        <select name="template_id" class="input" aria-label="${esc(t('as_template'))}">${opt('', t('as_all_templates'), state.template_id)}
          ${templates.map(x => opt(x.id, x.name, state.template_id)).join('')}</select>
        ${can('candidate.view_all') ? '' : `<label class="meta"><input type="checkbox" name="mine"${state.mine ? ' checked' : ''}> ${esc(t('as_only_mine'))}</label>`}
      </div><div id="results">${list.assessments.length ? `<p class="meta">${esc(t('as_count', {n: list.total}))}</p>` + AssessmentForm.historyHtml([...list.assessments].reverse(), {showTrainee: true, newestFirst: true})
        + pagerHtml() : App.emptyHtml(t('as_none_filtered'))}</div></div>`;
    host.querySelectorAll('.filters select, .filters input').forEach(el => el.addEventListener('change', () => {
      state.status = host.querySelector('[name="status"]').value;
      state.template_id = host.querySelector('[name="template_id"]').value;
      const mine = host.querySelector('[name="mine"]');
      state.mine = !!(mine && mine.checked);
      state.page = 1;
      load();
    }));
  }

  App.onActions(host, {add: () => AssessmentForm.create(),
                       page: p => { state.page = p; load(); window.scrollTo({top: 0}); }});
  App.onRerender(() => list && render());
  load();
})();

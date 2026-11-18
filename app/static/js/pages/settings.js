/* Stammdaten: Kandidaten-Status + Sprachniveaus pflegen (system.manage). */
(() => {
  const {$, esc, t, api, toast} = App;
  const host = $('#page');
  const LISTS = [{kind: 'candidate-status', title: 'st_status_title'}, {kind: 'language-level', title: 'st_level_title'}];
  const entries = {};

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      const results = await Promise.all(LISTS.map(l => api('GET', `/api/catalogs/${l.kind}`)));
      LISTS.forEach((l, i) => { entries[l.kind] = results[i].entries; });
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function listHtml({kind, title}) {
    const rows = entries[kind].map(e => `<tr${e.active ? '' : ' class="archived"'}>
      <td class="c">${e.sort_order}</td><td class="nw"><code>${esc(e.code)}</code></td><td>${esc(e.name)}</td>
      <td><span class="badge ${e.active ? 'ok' : 'warn'}">${esc(t(e.active ? 'active' : 'inactive'))}</span></td>
      <td><div class="row-actions">
        <button class="btn ghost sm" type="button" data-action="edit" data-kind="${kind}" data-id="${e.id}">${esc(t('edit'))}</button>
        <button class="btn ${e.active ? 'danger' : 'ghost'} sm" type="button" data-action="toggle" data-kind="${kind}" data-id="${e.id}">${esc(t(e.active ? 'btn_deactivate' : 'btn_activate'))}</button>
      </div></td></tr>`).join('');
    return `<section class="card"><div class="pghead"><h2>${esc(t(title))}</h2>
      <div class="tools"><button class="btn sm" type="button" data-action="add" data-kind="${kind}">${esc(t('st_add'))}</button></div></div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th class="c">${esc(t('f_order'))}</th><th>${esc(t('f_code'))}</th>
      <th>${esc(t('f_label'))}</th><th>${esc(t('f_status'))}</th><th>${esc(t('th_actions'))}</th></tr></thead>
      <tbody>${rows}</tbody></table></div></section>`;
  }

  function render() {
    host.innerHTML = `<p class="hint">${esc(t('st_hint'))}</p>${LISTS.map(listHtml).join('')}`;
  }

  function openForm(kind, entry) {
    const next = Math.max(0, ...entries[kind].map(e => e.sort_order)) + 10;
    App.formDialog({
      title: t(entry ? 'st_edit_title' : 'st_add_title'),
      fields: [
        {name: 'code', label: t('f_code'), required: true, maxlength: 40, value: entry ? entry.code : ''},
        {name: 'name', label: t('f_label'), required: true, maxlength: 120, value: entry ? entry.name : ''},
        {name: 'sort_order', label: t('f_order'), type: 'number', min: 0, max: 10000, step: 1,
         value: String(entry ? entry.sort_order : next)},
      ],
      onSubmit: async values => {
        if (entry) await api('PATCH', `/api/catalogs/${kind}/${entry.id}`, values);
        else await api('POST', `/api/catalogs/${kind}`, values);
        toast(t('saved'));
        await load();
      },
    });
  }

  App.onActions(host, {
    add: (_, el) => openForm(el.dataset.kind),
    edit: (entryId, el) => openForm(el.dataset.kind, entries[el.dataset.kind].find(e => e.id === entryId)),
    toggle: async (entryId, el) => {
      const entry = entries[el.dataset.kind].find(e => e.id === entryId);
      try {
        await api('PATCH', `/api/catalogs/${el.dataset.kind}/${entryId}`, {active: !entry.active});
        toast(t('saved'));
        await load();
      } catch (err) {
        toast(err.message, 'error');
      }
    },
  });
  App.onRerender(() => Object.keys(entries).length && render());
  load();
})();

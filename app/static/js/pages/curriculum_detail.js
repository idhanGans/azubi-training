/* Curriculum eines Programms fuer ein Sprachniveau: Module in Reihenfolge. */
(() => {
  const {$, esc, t, can, api, fmtNum, toast} = App;
  const host = $('#page');
  const id = +host.dataset.curriculumId;
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', `/api/curricula/${id}`);
      render();
    } catch (err) {
      App.showError(host, err, err.status === 404 ? null : load);
    }
  }

  function rowHtml(m, index, count) {
    const editable = can('curriculum.edit');
    return `<tr${m.status === 'ARCHIVED' ? ' class="archived"' : ''}>
      <td class="c">${index + 1}</td>
      <td class="name"><a href="/modules/${m.id}">${esc(m.name)}</a></td>
      <td><span class="badge ${m.status === 'ACTIVE' ? 'ok' : m.status === 'ARCHIVED' ? 'warn' : ''}">${esc(t('status_' + m.status))}</span></td>
      <td class="c">${esc(fmtNum(m.duration_hours))}</td><td class="c">${m.learning_objectives.length}</td>
      <td class="c">${m.material_count}</td>
      <td>${editable ? `<div class="row-actions">
        <button class="btn ghost sm" type="button" data-action="up" data-id="${m.id}" aria-label="${esc(t('move_up'))}"${index === 0 ? ' disabled' : ''}>▲</button>
        <button class="btn ghost sm" type="button" data-action="down" data-id="${m.id}" aria-label="${esc(t('move_down'))}"${index === count - 1 ? ' disabled' : ''}>▼</button>
        <button class="btn ghost sm" type="button" data-action="edit" data-id="${m.id}">${esc(t('edit'))}</button></div>` : ''}</td></tr>`;
  }

  function render() {
    const c = data.curriculum;
    App.setPageTitle(t('cd_title', {program: c.program, level: c.level.name}),
                     [{href: '/curriculum', label: t('nav_curriculum')}]);
    const modules = data.modules;
    host.innerHTML = `<div class="card">
      <div class="pghead"><span class="badge ${c.status === 'ACTIVE' ? 'ok' : c.status === 'ARCHIVED' ? 'warn' : ''}">${esc(t('status_' + c.status))}</span>
        <span class="meta">${esc(t('cu_summary', {n: c.module_count, h: fmtNum(c.hours_total)}))}</span>
        <div class="tools">
          ${can('curriculum.edit') ? `<button class="btn ghost sm" type="button" data-action="editCurriculum">${esc(t('cd_edit'))}</button>` : ''}
          ${can('curriculum.create') ? `<button class="btn sm" type="button" data-action="add">${esc(t('cd_add_module'))}</button>` : ''}
        </div></div>
      ${c.description ? `<p>${esc(c.description)}</p>` : ''}
      ${modules.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th class="c">${esc(t('th_pos'))}</th>
        <th>${esc(t('f_name'))}</th><th>${esc(t('f_status'))}</th><th class="c">${esc(t('th_hours'))}</th>
        <th class="c">${esc(t('th_objectives'))}</th><th class="c">${esc(t('th_materials'))}</th><th>${esc(t('th_actions'))}</th></tr></thead>
        <tbody>${modules.map((m, i) => rowHtml(m, i, modules.length)).join('')}</tbody></table></div>` : App.emptyHtml(t('cd_empty'))}
    </div>`;
  }

  async function move(moduleId, delta) {
    const order = ModuleForm.moved(data.modules.map(m => m.id), moduleId, delta);
    if (!order) return;
    try {
      await api('PUT', `/api/curricula/${id}/module-order`, {module_ids: order});
      await load();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  App.onActions(host, {
    add: () => ModuleForm.open({curriculumId: id, onSaved: load}),
    edit: moduleId => ModuleForm.open({module: data.modules.find(m => m.id === moduleId), onSaved: load}),
    up: moduleId => move(moduleId, -1),
    down: moduleId => move(moduleId, 1),
    editCurriculum: () => App.formDialog({
      title: t('cd_edit'),
      fields: [
        {name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000, value: data.curriculum.description},
        {name: 'status', label: t('f_status'), type: 'select', value: data.curriculum.status,
         options: ModuleForm.STATUSES.map(s => ({value: s, label: t('status_' + s)}))},
      ],
      onSubmit: async values => { await api('PATCH', `/api/curricula/${id}`, values); toast(t('saved')); await load(); },
    }),
  });
  App.onRerender(() => data && render());
  load();
})();

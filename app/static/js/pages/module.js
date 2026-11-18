/* Modul: Lernziele + Lernmaterial (Link oder Datei; Dateien nur ueber die geschuetzte Route). */
(() => {
  const {$, esc, t, can, api, fmtNum, fmtDateTime, toast} = App;
  const host = $('#page');
  const id = +host.dataset.moduleId;
  const ICONS = {PDF: 'file', VIDEO: 'play', DOCUMENT: 'file', LINK: 'link', IMAGE: 'image', EXERCISE: 'pen', HOMEWORK: 'home'};
  const TYPES = Object.keys(ICONS);
  const FILE_ONLY = ['PDF', 'DOCUMENT', 'IMAGE'];
  let data = null;
  let showArchived = false;

  const fmtBytes = n => (n >= 1048576 ? fmtNum(n / 1048576, 1) + ' MB' : fmtNum(Math.max(1, Math.round(n / 1024)), 0) + ' KB');
  const active = () => data.materials.filter(m => !m.archived_at);

  async function load() {
    try {
      data = await api('GET', `/api/modules/${id}` + (showArchived ? '?archived=1' : ''));
      render();
    } catch (err) {
      App.showError(host, err, err.status === 404 ? null : load);
    }
  }

  function materialHtml(m, index, count) {
    const archived = !!m.archived_at;
    const href = m.has_file ? `/api/materials/${m.id}/file` : m.url;
    const source = m.has_file ? `${esc(m.file_name)} · ${esc(fmtBytes(m.size_bytes))}` : m.url ? esc(new URL(m.url).host) : '';
    const edit = can('curriculum.edit');
    return `<div class="material${archived ? ' archived' : ''}">
      <span class="icon">${App.icon(ICONS[m.type])}</span>
      <div class="body">
        <b>${href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(m.title)}</a>` : esc(m.title)}</b>
        <span class="badge">${esc(t('type_' + m.type))}</span>
        ${m.team_only ? `<span class="badge draft">${App.icon('lock')} ${esc(t('mo_badge_team'))}</span>` : ''} ${archived ? `<span class="badge warn">${esc(t('archived'))}</span>` : ''}
        ${source ? `<span class="meta">${source}</span>` : ''}
        ${m.description ? `<p class="wrap-text">${esc(m.description)}</p>` : ''}
        <div class="meta">${esc(fmtDateTime(m.updated_at || m.created_at))}${m.updated_by || m.created_by ? ' · ' + esc(m.updated_by || m.created_by) : ''}</div>
      </div>
      ${edit ? `<div class="row-actions">${archived ? `<button class="btn ghost sm" type="button" data-action="restore" data-id="${m.id}">${esc(t('btn_restore'))}</button>` : `
        <button class="btn ghost sm" type="button" data-action="up" data-id="${m.id}" aria-label="${esc(t('move_up'))}"${index === 0 ? ' disabled' : ''}>▲</button>
        <button class="btn ghost sm" type="button" data-action="down" data-id="${m.id}" aria-label="${esc(t('move_down'))}"${index === count - 1 ? ' disabled' : ''}>▼</button>
        <button class="btn ghost sm" type="button" data-action="edit" data-id="${m.id}">${esc(t('edit'))}</button>
        ${m.has_file ? `<button class="btn ghost sm" type="button" data-action="replace" data-id="${m.id}">${esc(t('mo_replace'))}</button>` : ''}
        <button class="btn danger sm" type="button" data-action="archive" data-id="${m.id}">${esc(t('btn_archive'))}</button>`}</div>` : ''}
    </div>`;
  }

  function render() {
    const m = data.module;
    App.setPageTitle(m.name, [{href: '/curriculum', label: t('nav_curriculum')},
      {href: `/curriculum/${m.curriculum_id}`, label: t('cd_title', {program: m.program, level: m.level.name})}]);
    const list = active();
    const shown = showArchived ? data.materials : list;
    host.innerHTML = `
      <div class="card"><div class="pghead">
        <span class="badge ${m.status === 'ACTIVE' ? 'ok' : m.status === 'ARCHIVED' ? 'warn' : ''}">${esc(t('status_' + m.status))}</span>
        <span class="badge">${esc(m.level.code)}</span>
        ${m.duration_hours ? `<span class="meta">${esc(t('mo_duration', {h: fmtNum(m.duration_hours)}))}</span>` : ''}
        ${can('curriculum.edit') ? `<div class="tools"><button class="btn sm" type="button" data-action="editModule">${esc(t('edit'))}</button></div>` : ''}
      </div>${m.description ? `<p class="wrap-text">${esc(m.description)}</p>` : ''}</div>
      <section class="card"><h3>${esc(t('mo_objectives'))}</h3>
        ${m.learning_objectives.length ? `<ol class="objectives">${m.learning_objectives.map(o => `<li>${esc(o)}</li>`).join('')}</ol>`
          : App.emptyHtml(t('mo_no_objectives'))}</section>
      <section class="card"><div class="pghead"><h3 class="flush">${esc(t('mo_materials'))}</h3>
        <div class="tools"><label class="meta"><input type="checkbox" id="show-archived"${showArchived ? ' checked' : ''}> ${esc(t('mo_show_archived'))}</label>
        ${can('curriculum.create') ? `<button class="btn sm" type="button" data-action="add">${esc(t('mo_add_material'))}</button>` : ''}</div></div>
        ${shown.length ? shown.map(x => materialHtml(x, list.indexOf(x), list.length)).join('') : App.emptyHtml(t('mo_no_materials'))}
      </section>`;
    $('#show-archived').addEventListener('change', ev => { showArchived = ev.target.checked; load(); });
  }

  function fileField(type) {
    const ext = data.upload_rules.extensions[type].map(e => '.' + e);
    return {name: 'file', label: t('f_file'), type: 'file', required: FILE_ONLY.includes(type), accept: ext.join(','),
            hint: t('f_file_hint', {ext: ext.join(', '), mb: data.upload_rules.max_mb})};
  }

  const audienceField = teamOnly => ({name: 'team_only', label: t('mo_audience'), type: 'checks',
    options: [{value: 'true', label: t('mo_team_only')}], value: teamOnly ? ['true'] : []});

  function addMaterial(type) {
    const fields = [{name: 'title', label: t('f_title'), required: true, maxlength: 200}];
    if (!FILE_ONLY.includes(type)) {
      fields.push({name: 'url', label: t('f_url'), type: 'url', required: type === 'LINK', maxlength: 1000,
                   placeholder: 'https://', hint: type === 'LINK' ? '' : t('f_link_or_file')});
    }
    if (type !== 'LINK') fields.push(fileField(type));
    fields.push({name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000});
    fields.push(audienceField(false));
    App.formDialog({
      title: t('dlg_material_add', {type: t('type_' + type)}), fields,
      onSubmit: async (values, formData) => {
        const file = formData.get('file');
        const hasFile = file && file.size > 0;
        const teamOnly = formData.has('team_only');
        if (hasFile && values.url) throw new App.ApiError(400, t('f_link_or_file'), 'url');
        if (hasFile) {
          formData.set('type', type);
          formData.set('team_only', teamOnly ? 'true' : 'false');
          if (!values.url) formData.delete('url');
          await api('POST', `/api/modules/${id}/materials`, formData);
        } else {
          await api('POST', `/api/modules/${id}/materials`, {type, title: values.title, url: values.url,
                                                             description: values.description, team_only: teamOnly});
        }
        toast(t('saved'));
        await load();
      },
    });
  }

  function chooseType() {
    const dlg = App.openDialog(t('mo_choose_type'), `<div class="type-choices">${TYPES.map(type =>
      `<button class="btn ghost" type="button" data-type="${type}">${App.icon(ICONS[type])} ${esc(t('type_' + type))}</button>`).join('')}</div>`, true);
    dlg.addEventListener('click', ev => {
      const btn = ev.target.closest('[data-type]');
      if (!btn) return;
      dlg.close();
      addMaterial(btn.dataset.type);
    });
  }

  async function move(materialId, delta) {
    const order = ModuleForm.moved(active().map(m => m.id), materialId, delta);
    if (!order) return;
    try { await api('PUT', `/api/modules/${id}/material-order`, {material_ids: order}); await load(); }
    catch (err) { toast(err.message, 'error'); }
  }

  async function post(url, message) {
    try { await api('POST', url); toast(message); await load(); } catch (err) { toast(err.message, 'error'); }
  }

  const byId = mid => data.materials.find(m => m.id === mid);
  App.onActions(host, {
    add: chooseType,
    editModule: () => ModuleForm.open({module: data.module, onSaved: load}),
    up: mid => move(mid, -1),
    down: mid => move(mid, 1),
    edit: mid => {
      const m = byId(mid);
      const fields = [{name: 'title', label: t('f_title'), required: true, maxlength: 200, value: m.title}];
      if (!m.has_file && !FILE_ONLY.includes(m.type)) {
        fields.push({name: 'url', label: t('f_url'), type: 'url', required: m.type === 'LINK', maxlength: 1000, value: m.url || ''});
      }
      fields.push({name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000, value: m.description});
      fields.push(audienceField(m.team_only));
      App.formDialog({title: t('dlg_material_edit'), fields,
        onSubmit: async (values, formData) => {
          await api('PATCH', `/api/materials/${mid}`, {...values, team_only: formData.has('team_only')});
          toast(t('saved')); await load();
        }});
    },
    replace: mid => {
      const m = byId(mid);
      App.formDialog({title: t('dlg_replace_file', {name: m.title}), fields: [{...fileField(m.type), required: true}],
        onSubmit: async (_, formData) => { await api('POST', `/api/materials/${mid}/file`, formData); toast(t('saved')); await load(); }});
    },
    archive: async mid => {
      if (await App.confirmDialog(t('confirm_archive_material', {name: byId(mid).title}))) post(`/api/materials/${mid}/archive`, t('saved'));
    },
    restore: mid => post(`/api/materials/${mid}/restore`, t('saved')),
  });
  App.onRerender(() => data && render());
  host.innerHTML = App.loadingHtml();
  load();
})();

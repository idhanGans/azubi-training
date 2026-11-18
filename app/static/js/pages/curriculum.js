/* Curriculum-Uebersicht: Programme mit ihren Sprachniveaus/Curricula. */
(() => {
  const {$, esc, t, can, api, fmtNum, toast} = App;
  const host = $('#page');
  let programs = null;
  let levels = [];

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      const [p, l] = await Promise.all([api('GET', '/api/programs'), api('GET', '/api/catalogs/language-level')]);
      programs = p.programs;
      levels = l.entries;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function curriculumHtml(c) {
    return `<a class="level-card" href="/curriculum/${c.id}">
      <span class="level-code">${esc(c.level.code)}</span>
      <span><span class="badge ${c.status === 'ACTIVE' ? 'ok' : c.status === 'ARCHIVED' ? 'warn' : ''}">${esc(t('status_' + c.status))}</span>
      <span class="meta">${esc(t('cu_summary', {n: c.module_count, h: fmtNum(c.hours_total)}))}</span></span></a>`;
  }

  function programHtml(p) {
    const editable = can('curriculum.edit');
    return `<section class="card">
      <div class="pghead"><h2>${esc(p.name)} ${p.active ? '' : `<span class="badge warn">${esc(t('cu_inactive'))}</span>`}</h2>
        <div class="tools">
          ${can('curriculum.create') ? `<button class="btn ghost sm" type="button" data-action="addLevel" data-id="${p.id}">${esc(t('cu_add_level'))}</button>` : ''}
          ${editable ? `<button class="btn ghost sm" type="button" data-action="editProgram" data-id="${p.id}">${esc(t('edit'))}</button>` : ''}
        </div></div>
      ${p.description ? `<p class="mut">${esc(p.description)}</p>` : ''}
      ${p.curricula.length ? `<div class="level-grid">${p.curricula.map(curriculumHtml).join('')}</div>` : App.emptyHtml(t('cu_no_levels'))}
    </section>`;
  }

  function render() {
    host.innerHTML = `<div class="pghead"><p class="hint inline">${esc(t('cu_hint'))}</p>
      ${can('curriculum.create') ? `<div class="tools"><button class="btn sm" type="button" data-action="addProgram">${esc(t('cu_add_program'))}</button></div>` : ''}</div>
      ${programs.length ? programs.map(programHtml).join('') : `<div class="card">${App.emptyHtml(t('cu_empty'))}</div>`}`;
  }

  function programForm(p) {
    const fields = [
      {name: 'name', label: t('f_name'), required: true, maxlength: 120, value: p ? p.name : ''},
      {name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000, value: p ? p.description : ''},
    ];
    if (p) fields.push({name: 'active', label: t('f_active_program'), type: 'select', value: p.active ? '1' : '',
                        options: [{value: '1', label: t('active')}, {value: '', label: t('inactive')}]});
    App.formDialog({
      title: t(p ? 'dlg_program_edit' : 'dlg_program_add'), fields,
      onSubmit: async values => {
        if (p) await api('PATCH', `/api/programs/${p.id}`, {...values, active: values.active === '1'});
        else await api('POST', '/api/programs', values);
        toast(t('saved'));
        await load();
      },
    });
  }

  App.onActions(host, {
    addProgram: () => programForm(null),
    editProgram: id => programForm(programs.find(p => p.id === id)),
    addLevel: id => {
      const program = programs.find(p => p.id === id);
      const taken = new Set(program.curricula.map(c => c.level.id));
      const free = levels.filter(l => l.active && !taken.has(l.id));
      App.formDialog({
        title: t('dlg_level_add'),
        fields: [{name: 'level_id', label: t('th_level'), type: 'select', required: true, value: '',
                  options: [{value: '', label: '–'}, ...free.map(l => ({value: String(l.id), label: l.name}))]}],
        onSubmit: async values => {
          const created = await api('POST', `/api/programs/${id}/curricula`, values);
          App.goWithToast(`/curriculum/${created.id}`, t('saved'));
        },
      });
    },
  });
  App.onRerender(() => programs && render());
  load();
})();

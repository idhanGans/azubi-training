/* Kurs-Formular (Anlegen + Bearbeiten). Modul- und Dozenten-Auswahl haengen am
   Sprachniveau und werden bei dessen Wechsel neu geladen. Die Regeln selbst
   (Modul passt zum Niveau, Dozent aktiv + unterrichtet das Niveau) prueft der Server. */
const CourseForm = (() => {
  const {esc, t, api} = App;
  const STATUSES = ['PLANNED', 'RUNNING', 'COMPLETED'];

  const optionsHtml = (list, current) => [`<option value="">${esc(t('opt_none'))}</option>`,
    ...list.map(o => `<option value="${esc(o.value)}"${o.value === current ? ' selected' : ''}>${esc(o.label)}</option>`)].join('');

  async function choices(levelId, course) {
    if (!levelId) return {modules: [], instructors: []};
    const [mods, inst] = await Promise.all([api('GET', `/api/modules?level_id=${levelId}`), api('GET', '/api/instructors')]);
    const modules = mods.modules.map(m => ({value: String(m.id), label: `${m.program} – ${m.name}`}));
    const instructors = inst.instructors
      .filter(i => i.status === 'ACTIVE' && i.levels.some(l => l.id === +levelId))
      .map(i => ({value: String(i.id), label: i.name}));
    // Bisherige Zuordnung bleibt sichtbar, auch wenn sie heute nicht mehr waehlbar waere.
    if (course && +levelId === course.level_id) {
      if (course.module && !modules.some(m => +m.value === course.module.id)) {
        modules.push({value: String(course.module.id), label: `${course.module.program} – ${course.module.name}`});
      }
      if (course.instructor && !instructors.some(i => +i.value === course.instructor.id)) {
        instructors.push({value: String(course.instructor.id), label: `${course.instructor.name} ${t('opt_inactive')}`});
      }
    }
    return {modules, instructors};
  }

  async function open({course, levels, onSaved}) {
    const c = course;
    const levelId = c ? String(c.level_id) : '';
    const initial = await choices(levelId, c);
    const dlg = App.formDialog({
      title: t(c ? 'dlg_course_edit' : 'dlg_course_add'),
      fields: [
        {name: 'name', label: t('f_name'), required: true, maxlength: 160, value: c ? c.name : '', placeholder: t('ph_course_name')},
        {name: 'level_id', label: t('th_level'), type: 'select', required: true, value: levelId,
         options: [{value: '', label: t('opt_choose')}, ...levels.filter(l => l.active || String(l.id) === levelId)
           .map(l => ({value: String(l.id), label: l.name}))]},
        {name: 'module_id', label: t('f_current_module'), type: 'select', value: c && c.module_id ? String(c.module_id) : '',
         options: [{value: '', label: t('opt_none')}, ...initial.modules], hint: t('co_module_hint')},
        {name: 'instructor_id', label: t('f_instructor'), type: 'select', value: c && c.instructor_id ? String(c.instructor_id) : '',
         options: [{value: '', label: t('opt_none')}, ...initial.instructors], hint: t('co_instructor_hint')},
        {name: 'status', label: t('f_status'), type: 'select', value: c ? c.status : 'PLANNED',
         options: STATUSES.map(s => ({value: s, label: t('cs_' + s)}))},
        {name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000, value: c ? c.description : ''},
      ],
      onSubmit: async values => {
        const body = {...values, level_id: +values.level_id, module_id: values.module_id ? +values.module_id : null,
                      instructor_id: values.instructor_id ? +values.instructor_id : null};
        const saved = c ? await api('PATCH', `/api/courses/${c.id}`, body) : await api('POST', '/api/courses', body);
        App.toast(t('saved'));
        await onSaved(saved);
      },
    });
    dlg.querySelector('[name="level_id"]').addEventListener('change', async ev => {
      const moduleSel = dlg.querySelector('[name="module_id"]'), instSel = dlg.querySelector('[name="instructor_id"]');
      try {
        const next = await choices(ev.target.value, c);
        moduleSel.innerHTML = optionsHtml(next.modules, moduleSel.value);
        instSel.innerHTML = optionsHtml(next.instructors, instSel.value);
      } catch (err) {
        App.showFormError(dlg.querySelector('form'), err);
      }
    });
  }

  const statusBadge = status => `<span class="badge ${status === 'RUNNING' ? 'ok' : ''}">${esc(t('cs_' + status))}</span>`;

  return {open, statusBadge, STATUSES};
})();

/* Modul-Formular (Anlegen + Bearbeiten); Lernziele: eines pro Zeile. */
const ModuleForm = (() => {
  const {t, api} = App;
  const STATUSES = ['DRAFT', 'ACTIVE', 'ARCHIVED'];

  function open({curriculumId, module, onSaved}) {
    App.formDialog({
      title: t(module ? 'dlg_module_edit' : 'dlg_module_add'),
      fields: [
        {name: 'name', label: t('f_name'), required: true, maxlength: 160, value: module ? module.name : '',
         placeholder: 'Modul 8 – Konjunktiv II'},
        {name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000,
         value: module ? module.description : ''},
        {name: 'duration_hours', label: t('f_duration'), type: 'number', min: 0.5, max: 1000, step: 0.5,
         value: module && module.duration_hours != null ? String(module.duration_hours) : ''},
        {name: 'learning_objectives', label: t('f_objectives'), type: 'textarea', rows: 5, hint: t('f_objectives_hint'),
         value: module ? module.learning_objectives.join('\n') : ''},
        {name: 'status', label: t('f_status'), type: 'select', value: module ? module.status : 'DRAFT',
         options: STATUSES.map(s => ({value: s, label: t('status_' + s)}))},
      ],
      onSubmit: async values => {
        const body = {...values, learning_objectives: values.learning_objectives.split('\n').map(s => s.trim()).filter(Boolean)};
        const saved = module ? await api('PATCH', `/api/modules/${module.id}`, body)
                             : await api('POST', `/api/curricula/${curriculumId}/modules`, body);
        App.toast(t('saved'));
        await onSaved(saved);
      },
    });
  }

  /* Eintrag um eine Position verschieben -> neue ID-Reihenfolge (oder null am Rand). */
  function moved(ids, id, delta) {
    const i = ids.indexOf(id), j = i + delta;
    if (i < 0 || j < 0 || j >= ids.length) return null;
    const next = ids.slice();
    [next[i], next[j]] = [next[j], next[i]];
    return next;
  }

  return {open, moved, STATUSES};
})();

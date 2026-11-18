/* Kandidaten-Formular (Anlegen + Bearbeiten) und Stammdaten-Auswahllisten. */
const CandidateForm = (() => {
  const {t, api} = App;
  const FACH = ['Elektro', 'SHK'];
  let catalogs = null;

  async function loadCatalogs() {
    if (!catalogs) {
      const [status, level, programs, departments] = await Promise.all([
        api('GET', '/api/catalogs/candidate-status'), api('GET', '/api/catalogs/language-level'),
        App.can('curriculum.view') ? api('GET', '/api/programs') : Promise.resolve({programs: []}),
        api('GET', '/api/departments')]);
      catalogs = {status: status.entries, level: level.entries, program: programs.programs, department: departments.departments};
    }
    return catalogs;
  }

  /* Auswahl: aktive Eintraege + der aktuell gespeicherte (auch wenn inaktiv). */
  function options(entries, currentId) {
    return [{value: '', label: t('opt_none')}, ...entries
      .filter(e => e.active || e.id === currentId)
      .map(e => ({value: String(e.id), label: e.name + (e.active ? '' : ' ' + t('opt_inactive'))}))];
  }

  function fields(c, cats) {
    const val = key => (c && c[key] != null ? String(c[key]) : '');
    return [
      {heading: t('cp_personal')},
      {name: 'name', label: t('f_name'), required: true, maxlength: 200, value: val('name')},
      {name: 'nickname', label: t('f_nickname'), maxlength: 120, value: val('nickname')},
      {name: 'email', label: t('f_email'), type: 'email', maxlength: 200, value: val('email')},
      {name: 'phone', label: t('f_phone'), type: 'tel', maxlength: 40, value: val('phone'), placeholder: '+62 812 3456 789'},
      {name: 'date_of_birth', label: t('f_birth'), type: 'date', value: val('date_of_birth')},
      {heading: t('cp_training_info')},
      {name: 'status_id', label: t('f_status'), type: 'select', value: val('status_id'),
       options: options(cats.status, c && c.status_id)},
      ...(cats.program.length ? [{name: 'program_id', label: t('f_program'), type: 'select',
        value: val('program_id'), options: options(cats.program, c && c.program_id)}] : []),
      {name: 'fach', label: t('f_fach'), type: 'select', value: val('fach'),
       options: [{value: '', label: t('opt_none')}, ...FACH.map(f => ({value: f, label: f}))]},
      {name: 'target_occupation', label: t('f_target_occupation'), maxlength: 120, value: val('target_occupation'),
       placeholder: 'Elektroniker/in für Energie- und Gebäudetechnik'},
      {name: 'department_id', label: t('f_department'), type: 'select', value: val('department_id'),
       options: options(cats.department, c && c.department_id), hint: t('f_department_hint')},
      {name: 'abteilung', label: t('f_abteilung'), maxlength: 80, value: val('abteilung'), placeholder: 'Berlin – PV-Assistent'},
      {name: 'supervisor', label: t('ov_th_spv'), maxlength: 120, value: val('supervisor'), placeholder: 'arif_rahman',
       hint: t('f_supervisor_hint')},
      {name: 'start_date', label: t('f_start'), type: 'date', value: val('start_date')},
      {name: 'expected_completion_date', label: t('f_end'), type: 'date', value: val('expected_completion_date')},
      {heading: t('cp_language')},
      {name: 'current_level_id', label: t('f_level_current'), type: 'select', value: val('current_level_id'),
       options: options(cats.level, c && c.current_level_id)},
      {name: 'target_level_id', label: t('f_level_target'), type: 'select', value: val('target_level_id'),
       options: options(cats.level, c && c.target_level_id)},
      {heading: t('f_login')},
      {name: 'msh_user', label: t('f_login'), maxlength: 120, value: val('msh_user'), hint: t('f_login_hint')},
    ];
  }

  /* Oeffnet den Dialog; onSaved(candidate) nach erfolgreichem Speichern. */
  async function open(candidate, onSaved) {
    const cats = await loadCatalogs();
    App.formDialog({
      title: t(candidate ? 'dlg_edit_candidate' : 'dlg_add_candidate'),
      fields: fields(candidate, cats),
      onSubmit: async values => {
        const saved = candidate
          ? await api('PATCH', `/api/candidates/${candidate.id}`, values)
          : await api('POST', '/api/candidates', values);
        App.toast(t('saved'));
        await onSaved(saved);
      },
    });
  }

  return {open, loadCatalogs, FACH};
})();

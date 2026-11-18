/* Dozenten-Formular (Anlegen + Bearbeiten) inkl. Wochen-Verfuegbarkeit, plus Anzeige-Helfer. */
const InstructorForm = (() => {
  const {esc, t, api} = App;
  const STATUSES = ['ACTIVE', 'ON_LEAVE', 'INACTIVE'];
  const DAYS = [0, 1, 2, 3, 4, 5, 6];

  function weekHtml(slots) {
    const byDay = Object.fromEntries((slots || []).map(s => [s.weekday, s]));
    return `<div class="week">${DAYS.map(d => `<div class="week-row">
      <span class="week-day">${esc(t('wd_' + d))}</span>
      <input class="input" type="time" name="av_${d}_start" value="${esc(byDay[d] ? byDay[d].start : '')}" aria-label="${esc(t('av_from', {day: t('wd_' + d)}))}">
      <span aria-hidden="true">–</span>
      <input class="input" type="time" name="av_${d}_end" value="${esc(byDay[d] ? byDay[d].end : '')}" aria-label="${esc(t('av_to', {day: t('wd_' + d)}))}">
    </div>`).join('')}</div>`;
  }

  /* Formularwerte -> Liste {weekday, start, end}; halb ausgefuellte Tage sind ein Fehler. */
  function readWeek(values) {
    const slots = [];
    for (const d of DAYS) {
      const start = values[`av_${d}_start`], end = values[`av_${d}_end`];
      delete values[`av_${d}_start`];
      delete values[`av_${d}_end`];
      if (!start && !end) continue;
      if (!start || !end) throw new App.ApiError(400, t('av_incomplete', {day: t('wd_' + d)}), 'availability');
      slots.push({weekday: d, start, end});
    }
    return slots;
  }

  function open({instructor, levels, onSaved}) {
    const i = instructor;
    const val = key => (i && i[key] != null ? String(i[key]) : '');
    const current = i ? i.levels.map(l => String(l.id)) : [];
    App.formDialog({
      title: t(i ? 'dlg_instructor_edit' : 'dlg_instructor_add'),
      fields: [
        {name: 'name', label: t('f_name'), required: true, maxlength: 200, value: val('name')},
        {name: 'email', label: t('f_email'), type: 'email', maxlength: 200, value: val('email')},
        {name: 'msh_user', label: t('f_login'), maxlength: 120, value: val('msh_user'), hint: t('in_login_hint')},
        {name: 'qualification', label: t('f_qualification'), type: 'textarea', maxlength: 2000, value: val('qualification')},
        {name: 'specialization', label: t('f_specialization'), maxlength: 200, value: val('specialization'),
         placeholder: t('ph_specialization')},
        {name: 'level_ids', label: t('f_levels_taught'), type: 'checks', value: current,
         options: levels.filter(l => l.active || current.includes(String(l.id)))
           .map(l => ({value: String(l.id), label: l.name + (l.active ? '' : ' ' + t('opt_inactive'))}))},
        {name: 'availability', label: t('f_availability'), type: 'custom', html: weekHtml(i && i.availability),
         hint: t('av_hint')},
        {name: 'status', label: t('f_status'), type: 'select', value: i ? i.status : 'ACTIVE',
         options: STATUSES.map(s => ({value: s, label: t('is_' + s)}))},
      ],
      onSubmit: async (values, formData) => {
        const availability = readWeek(values);   // entfernt die av_*-Felder aus values
        const body = {...values, availability, level_ids: formData.getAll('level_ids').map(Number)};
        const saved = i ? await api('PATCH', `/api/instructors/${i.id}`, body) : await api('POST', '/api/instructors', body);
        App.toast(t('saved'));
        await onSaved(saved);
      },
    });
  }

  /* „Mo 08:00–12:00, Mi 13:00–17:00" */
  const weekText = slots => (slots && slots.length
    ? slots.map(s => `${t('wd_' + s.weekday)} ${s.start}–${s.end}`).join(', ') : '–');
  const statusBadge = status => `<span class="badge ${status === 'ACTIVE' ? 'ok' : status === 'INACTIVE' ? 'warn' : ''}">${esc(t('is_' + status))}</span>`;

  return {open, weekText, statusBadge, STATUSES};
})();

/* Sessions: form (create/edit), detail dialog with actions, card display.
   The server checks time conflicts and availability; here it is only displayed. */
const SessionForm = (() => {
  const {esc, t, can, api, fmtDate, fmtTimeRange, toast} = App;

  const optionList = (list, current) => [{value: '', label: t('opt_none')}, ...list].map(o => ({...o, selected: o.value === current}));  // selected: only for fill()

  async function choices(course, session) {
    const [mods, inst] = await Promise.all([
      api('GET', `/api/modules?level_id=${course.level.id}`),
      can('instructor.view') ? api('GET', '/api/instructors') : Promise.resolve({instructors: []})]);
    const modules = mods.modules.map(m => ({value: String(m.id), label: `${m.program} – ${m.name}`}));
    const instructors = inst.instructors.filter(i => i.status === 'ACTIVE' && i.levels.some(l => l.id === course.level.id))
      .map(i => ({value: String(i.id), label: i.name}));
    const keep = (list, ref, label) => { if (ref && !list.some(o => +o.value === ref.id)) list.push({value: String(ref.id), label}); };
    if (session) {
      keep(modules, session.module, session.module && session.module.name);
      keep(instructors, session.instructor, session.instructor && `${session.instructor.name} ${t('opt_inactive')}`);
    }
    return {modules, instructors};
  }

  /* course: {id, name, level}; session: existing session or null; courses: selection, if no course is given. */
  async function open({course, session, courses, date, onSaved}) {
    let current = course || (session && session.course) || null;
    const base = current ? await choices(current, session) : {modules: [], instructors: []};
    const val = key => (session && session[key] != null ? String(session[key]) : '');
    const fields = [];
    if (!session && !course) {
      fields.push({name: 'course_id', label: t('f_course'), type: 'select', required: true, value: '',
                   options: [{value: '', label: t('opt_choose')}, ...courses.map(c => ({value: String(c.id), label: `${c.name} (${c.level.code})`}))]});
    }
    fields.push(
      {name: 'date', label: t('f_date'), type: 'date', required: true, value: session ? session.date : (date || '')},
      {name: 'start', label: t('f_start_time'), type: 'time', required: true, value: val('start')},
      {name: 'end', label: t('f_end_time'), type: 'time', required: true, value: val('end')},
      {name: 'module_id', label: t('page_module'), type: 'select',
       value: session ? val('module_id') : (current && current.module_id ? String(current.module_id) : ''),
       options: optionList(base.modules)},
      {name: 'instructor_id', label: t('f_instructor'), type: 'select',
       value: session ? val('instructor_id') : (current && current.instructor_id ? String(current.instructor_id) : ''),
       options: optionList(base.instructors)},
      {name: 'room', label: t('f_room'), maxlength: 80, value: val('room')},
      {name: 'location', label: t('f_location'), maxlength: 200, value: val('location')},
      {name: 'online_url', label: t('f_online_url'), type: 'url', maxlength: 1000, value: val('online_url'), placeholder: 'https://'},
      {name: 'notes', label: t('f_notes_internal'), type: 'textarea', maxlength: 4000, value: val('notes'), hint: t('se_notes_hint')},
    );
    if (!session) fields.push({name: 'repeat_until', label: t('f_repeat_until'), type: 'date', hint: t('se_repeat_hint')});
    const dlg = App.formDialog({
      title: t(session ? 'dlg_session_edit' : 'dlg_session_add'),
      intro: current ? current.name : null,
      fields,
      onSubmit: async values => {
        const body = {...values, module_id: values.module_id ? +values.module_id : null,
                      instructor_id: values.instructor_id ? +values.instructor_id : null};
        if (!body.repeat_until) delete body.repeat_until;
        let res;
        if (session) {
          res = await api('PATCH', `/api/sessions/${session.id}`, body);
        } else {
          body.course_id = current ? current.id : +values.course_id;
          res = await api('POST', '/api/sessions', body);
        }
        const n = res.sessions ? res.sessions.length : 1;
        toast(n > 1 ? t('se_created_n', {n}) : t('saved'));
        (res.warnings || []).forEach(w => toast(w, 'warn'));
        await onSaved(res);
      },
    });
    const courseSel = dlg.querySelector('[name="course_id"]');
    if (courseSel) {
      courseSel.addEventListener('change', async () => {
        current = courses.find(c => c.id === +courseSel.value) || null;
        const next = current ? await choices(current, null) : {modules: [], instructors: []};
        const fill = (name, list, preset) => {
          dlg.querySelector(`[name="${name}"]`).innerHTML = optionList(list, preset)
            .map(o => `<option value="${esc(o.value)}"${o.selected ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
        };
        fill('module_id', next.modules, current && current.module_id ? String(current.module_id) : '');
        fill('instructor_id', next.instructors, current && current.instructor_id ? String(current.instructor_id) : '');
      });
    }
  }

  function cancel(session, onSaved) {
    App.formDialog({
      title: t('se_cancel_title'),
      intro: `${session.course.name} · ${fmtDate(session.date)} ${fmtTimeRange(session.start, session.end)}`,
      fields: [{name: 'cancel_reason', label: t('f_cancel_reason'), type: 'textarea', required: true, maxlength: 500}],
      submitLabel: t('se_cancel'),
      onSubmit: async values => {
        await api('PATCH', `/api/sessions/${session.id}`, {status: 'CANCELLED', cancel_reason: values.cancel_reason});
        toast(t('se_cancelled'));
        await onSaved();
      },
    });
  }

  async function setStatus(session, status, onSaved) {
    try {
      const res = await api('PATCH', `/api/sessions/${session.id}`, {status});
      toast(t('saved'));
      (res.warnings || []).forEach(w => toast(w, 'warn'));
      await onSaved();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  const statusBadge = s => s.status === 'SCHEDULED' ? ''
    : `<span class="badge ${s.status === 'CANCELLED' ? 'warn' : 'ok'}">${esc(t('ss_' + s.status))}</span>`;

  const place = s => [s.room, s.location].filter(Boolean).join(' · ');

  /* Compact card for lists/calendar (clickable -> detail). */
  function cardHtml(s, {showDate} = {}) {
    return `<button type="button" class="sess${s.status === 'CANCELLED' ? ' cancelled' : ''}" data-action="session" data-id="${s.id}">
      <span class="sess-time">${showDate ? esc(fmtDate(s.date)) + ' · ' : ''}${esc(fmtTimeRange(s.start, s.end))}</span>
      <b>${esc(s.course.name)}</b> ${statusBadge(s)}
      <span class="meta">${esc([s.module && s.module.name, s.instructor && s.instructor.name, place(s)].filter(Boolean).join(' · '))}</span>
    </button>`;
  }

  /* Detail dialog with actions depending on permission. */
  function show(s, {onChanged, courses} = {}) {
    const edit = can('schedule.edit');
    // Attendance: from `attendance_from` (the rule lives only in the server), never for cancelled sessions
    const started = Date.parse(s.attendance_from) <= Date.now();
    const attendance = s.status !== 'CANCELLED' && started && typeof AttendanceForm !== 'undefined'
      ? (can('attendance.manage') ? 'at_record' : can('attendance.view') ? 'at_view' : null) : null;
    // Module rating: session with a module, not cancelled; capture from the start (same rule as attendance)
    const lesson = s.module && s.status !== 'CANCELLED' && can('assessment.view')
      ? (can('assessment.create') && started ? 'lr_record' : 'lr_view') : null;
    const row = (label, html) => html ? `<dt>${esc(t(label))}</dt><dd>${html}</dd>` : '';
    const dlg = App.openDialog(s.course.name, `<dl class="facts">
        ${row('f_date', esc(fmtDate(s.date)))}${row('f_time', esc(fmtTimeRange(s.start, s.end)))}
        ${row('f_duration_min', esc(t('se_minutes', {n: s.duration_minutes})))}
        ${row('th_level', esc(s.course.level.name))}${row('page_module', s.module ? esc(s.module.name) : '')}
        ${row('f_instructor', s.instructor ? esc(s.instructor.name) : esc(t('co_no_instructor')))}
        ${row('f_room', esc(s.room || ''))}${row('f_location', esc(s.location || ''))}
        ${row('f_online_url', s.online_url ? `<a href="${esc(s.online_url)}" target="_blank" rel="noopener noreferrer">${esc(t('se_join'))}</a>` : '')}
        ${row('th_participants', s.participant_count != null ? esc(String(s.participant_count)) : '')}
        ${row('f_status', esc(t('ss_' + s.status)) + (s.cancel_reason ? ` <span class="meta">– ${esc(s.cancel_reason)}</span>` : ''))}
        ${row('f_notes_internal', s.notes ? `<span class="wrap-text">${esc(s.notes)}</span>` : '')}
      </dl>
      <div class="form-actions">
        ${lesson ? `<a class="btn sm" href="/sessions/${s.id}/lesson">${esc(t(lesson))}</a>` : ''}
        ${attendance ? `<button class="btn ${lesson ? 'ghost ' : ''}sm" type="button" data-do="attendance">${esc(t(attendance))}</button>` : ''}
        ${can('schedule.view') ? `<a class="btn ghost sm" href="/courses/${s.course.id}">${esc(t('se_to_course'))}</a>` : ''}
        ${edit && s.status !== 'CANCELLED' ? `<button class="btn sm" type="button" data-do="edit">${esc(t('edit'))}</button>` : ''}
        ${edit && s.status === 'SCHEDULED' ? `<button class="btn ghost sm" type="button" data-do="done">${esc(t('se_mark_done'))}</button>` : ''}
        ${edit && s.status !== 'CANCELLED' ? `<button class="btn danger sm" type="button" data-do="cancel">${esc(t('se_cancel'))}</button>` : ''}
        ${edit && s.status === 'CANCELLED' ? `<button class="btn ghost sm" type="button" data-do="reactivate">${esc(t('se_reactivate'))}</button>` : ''}
      </div>`, true);
    const act = {
      attendance: () => AttendanceForm.open(s, onChanged),
      edit: () => open({session: s, courses, onSaved: onChanged}),
      done: () => setStatus(s, 'COMPLETED', onChanged),
      cancel: () => cancel(s, onChanged),
      reactivate: () => setStatus(s, 'SCHEDULED', onChanged),
    };
    dlg.querySelectorAll('[data-do]').forEach(b => b.addEventListener('click', () => { dlg.close(); act[b.dataset.do](); }));
  }

  return {open, show, cardHtml, statusBadge, place};
})();

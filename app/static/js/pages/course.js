/* Course: master data, instructor, module, participants (add/remove). */
(() => {
  const {$, esc, t, can, api, fmtDateTime, toast} = App;
  const host = $('#page');
  const id = +host.dataset.courseId;
  let data = null;
  let levels = [];
  let sessions = [];
  const SESSION_DAYS = 55;     // sessions of the next 8 weeks

  const fact = (label, html) => `<dt>${esc(t(label))}</dt><dd>${html || '–'}</dd>`;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      const from = App.todayIso(), to = App.days.add(from, SESSION_DAYS);
      const [body, lv, ses] = await Promise.all([api('GET', `/api/courses/${id}`), api('GET', '/api/catalogs/language-level'),
        api('GET', `/api/sessions?course_id=${id}&from=${from}&to=${to}&include_cancelled=1`)]);
      data = body;
      levels = lv.entries;
      sessions = ses.sessions;
      render();
    } catch (err) {
      App.showError(host, err, err.status === 404 ? null : load);
    }
  }

  function participantsHtml() {
    const edit = can('schedule.edit') && !data.course.archived_at;
    const rows = data.participants;
    if (!rows.length) return App.emptyHtml(t('co_no_participants'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_candidate_no'))}</th><th>${esc(t('f_name'))}</th>
      <th>${esc(t('th_level'))}</th><th>${esc(t('f_status'))}</th><th class="c">${esc(t('at_rate'))}</th><th>${esc(t('co_added'))}</th>${edit ? `<th>${esc(t('th_actions'))}</th>` : ''}</tr></thead>
      <tbody>${rows.map(p => `<tr${p.archived ? ' class="archived"' : ''}><td class="nw">${esc(p.candidate_no)}</td>
        <td class="name"><a href="/candidates/${p.id}">${esc(p.name)}</a>${p.archived ? ` <span class="badge warn">${esc(t('archived'))}</span>` : ''}</td>
        <td class="nw">${p.current_level ? `<span class="badge">${esc(p.current_level.code)}</span>` : '–'}</td>
        <td>${p.status ? esc(p.status.name) : '–'}</td>
        <td class="c nw" title="${p.attendance ? esc(AttendanceForm.countsText(p.attendance)) : ''}">${esc(AttendanceForm.rateText(p.attendance && p.attendance.rate))}</td>
        <td class="nw">${esc(fmtDateTime(p.added_at))}</td>
        ${edit ? `<td><button class="btn ghost sm" type="button" data-action="remove" data-id="${p.id}">${esc(t('co_remove'))}</button></td>` : ''}</tr>`).join('')}
      </tbody></table></div>`;
  }

  function render() {
    const c = data.course;
    const archived = !!c.archived_at;
    App.setPageTitle(c.name, [{href: '/courses', label: t('nav_courses')}]);
    const edit = can('schedule.edit');
    const moduleHtml = c.module ? (can('curriculum.view') ? `<a href="/modules/${c.module.id}">${esc(c.module.name)}</a>` : esc(c.module.name))
      + ` <span class="meta">${esc(c.module.program)}</span>` : '';
    const instructorHtml = c.instructor ? esc(c.instructor.name) + (c.instructor.status !== 'ACTIVE' || c.instructor.archived
      ? ` <span class="badge warn">${esc(t(c.instructor.archived ? 'archived' : 'is_' + c.instructor.status))}</span>` : '')
      : `<span class="mut">${esc(t('co_no_instructor'))}</span>`;
    host.innerHTML = `
      <div class="card"><div class="profile-head"><div>
        <h2>${esc(c.name)}</h2>
        <span class="badge">${esc(c.level.name)}</span> ${CourseForm.statusBadge(c.status)}
        ${archived ? `<span class="badge warn">${esc(t('archived'))}</span>` : ''}
        <p class="meta">${esc(App.stamp('cp_created', c.created_at, c.created_by))}
          ${c.updated_at ? ' · ' + esc(App.stamp('cp_updated', c.updated_at, c.updated_by)) : ''}</p>
      </div>${edit ? `<div class="tools">
        ${archived ? '' : `<button class="btn sm" type="button" data-action="edit">${esc(t('edit'))}</button>`}
        <button class="btn ${archived ? 'ghost' : 'danger'} sm" type="button" data-action="${archived ? 'restore' : 'archive'}">${esc(t(archived ? 'btn_restore' : 'btn_archive'))}</button>
      </div>` : ''}</div>
      <dl class="facts">${fact('th_level', esc(c.level.name))}${fact('f_current_module', moduleHtml)}${fact('f_instructor', instructorHtml)}
        ${fact('f_description', c.description ? `<span class="wrap-text">${esc(c.description)}</span>` : '')}</dl></div>
      <section class="card"><div class="pghead"><h3 class="flush">${esc(t('co_sessions'))}</h3>
        <div class="tools"><a class="btn ghost sm" href="/schedule?course_id=${c.id}">${esc(t('co_in_schedule'))}</a>
        ${can('schedule.create') && !archived ? `<button class="btn sm" type="button" data-action="addSession">${esc(t('se_add'))}</button>` : ''}</div></div>
        ${sessions.length ? `<div class="sess-list">${sessions.map(s => SessionForm.cardHtml(s, {showDate: true})).join('')}</div>`
          : App.emptyHtml(t('co_no_sessions'))}</section>
      <section class="card"><div class="pghead"><h3 class="flush">${esc(t('co_participants', {n: data.participants.length}))}</h3>
        ${edit && !archived ? `<div class="tools"><button class="btn sm" type="button" data-action="addParticipants">${esc(t('co_add_participants'))}</button></div>` : ''}</div>
        ${participantsHtml()}</section>`;
  }

  async function allCandidates() {
    const items = [];
    for (let page = 1; ; page++) {
      const res = await api('GET', `/api/candidates?per_page=100&page=${page}`);
      items.push(...res.items);
      if (items.length >= res.total || !res.items.length) return items;
    }
  }

  async function addParticipants() {
    let candidates;
    try { candidates = await allCandidates(); } catch (err) { toast(err.message, 'error'); return; }
    const present = new Set(data.participants.map(p => p.id));
    const free = candidates.filter(c => !present.has(c.id));
    if (!free.length) { toast(t('co_all_added'), 'error'); return; }
    const html = `<input class="input" type="search" data-filter placeholder="${esc(t('cl_search_ph'))}" aria-label="${esc(t('cl_search'))}">
      <div class="pick-list">${free.map(c => `<label data-text="${esc((c.name + ' ' + c.candidate_no + ' ' + (c.nickname || '')).toLowerCase())}">
        <input type="checkbox" name="trainee_ids" value="${c.id}"> <span>${esc(c.name)} <span class="meta">${esc(c.candidate_no)}
        ${c.current_level ? ' · ' + esc(c.current_level.code) : ''}</span></span></label>`).join('')}</div>`;
    const dlg = App.formDialog({
      title: t('co_add_participants'),
      fields: [{name: 'trainee_ids', label: t('nav_candidates'), type: 'custom', html}],
      submitLabel: t('co_add_submit'),
      onSubmit: async (_, formData) => {
        const res = await api('POST', `/api/courses/${id}/participants`, {trainee_ids: formData.getAll('trainee_ids').map(Number)});
        toast(t('co_added_n', {n: res.added.length}));
        await load();
      },
    });
    dlg.querySelector('[data-filter]').addEventListener('input', ev => {
      const q = ev.target.value.trim().toLowerCase();
      dlg.querySelectorAll('.pick-list label').forEach(el => { el.hidden = !!q && !el.dataset.text.includes(q); });
    });
  }

  async function post(url) {
    try { await api('POST', url); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
  }

  App.onActions(host, {
    edit: () => CourseForm.open({course: data.course, levels, onSaved: load}).catch(err => toast(err.message, 'error')),
    archive: async () => {
      if (await App.confirmDialog(t('co_confirm_archive', {name: data.course.name}))) await post(`/api/courses/${id}/archive`);
    },
    restore: () => post(`/api/courses/${id}/restore`),
    addParticipants,
    addSession: () => SessionForm.open({course: data.course, onSaved: load}).catch(err => toast(err.message, 'error')),
    session: sid => SessionForm.show(sessions.find(s => s.id === sid), {onChanged: load}),
    remove: async tid => {
      const p = data.participants.find(x => x.id === tid);
      if (!await App.confirmDialog(t('co_confirm_remove', {name: p.name, course: data.course.name}))) return;
      try { await api('DELETE', `/api/courses/${id}/participants/${tid}`); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
    },
  });
  App.onRerender(() => data && render());
  load();
})();

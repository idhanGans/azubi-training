/* Candidate profile: master data, training, language progress, attendance, assessments (history), leader ratings, reports. */
(() => {
  const {$, esc, t, can, api, fmtDate, fmtDateTime, fmtNum, toast} = App;
  const host = $('#page');
  const id = +host.dataset.candidateId;
  let data = null;
  let progress = null;
  let levels = [];

  const fact = (label, value) => `<dt>${esc(t(label))}</dt><dd>${value == null || value === '' ? '–' : esc(value)}</dd>`;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      const [body, cats, prog] = await Promise.all([api('GET', `/api/candidates/${id}`), CandidateForm.loadCatalogs(),
                                                    api('GET', `/api/candidates/${id}/progress`)]);
      data = body;
      progress = prog;
      levels = cats.level;
      render();
    } catch (err) {
      App.showError(host, err, err.status === 404 ? null : load);
    }
  }

  function levelPath(c) {
    const cur = c.current_level, target = c.target_level;
    if (!cur && !target) return `<p class="mut">–</p>`;
    const order = Object.fromEntries(levels.map(l => [l.id, l.sort_order]));
    const shown = levels.filter(l => l.active || (cur && l.id === cur.id) || (target && l.id === target.id));
    const steps = shown.map(l => {
      let cls = '';
      if (cur && l.id === cur.id) cls = 'current';
      else if (target && l.id === target.id) cls = 'target';
      else if (cur && order[l.id] < order[cur.id]) cls = 'done';
      return `<span class="level-step ${cls}">${esc(l.code)}</span>`;
    }).join('<span aria-hidden="true" class="mut">›</span>');
    return `<div class="level-path" role="img" aria-label="${esc(t('cp_level_path', {a: cur ? cur.code : '–', b: target ? target.code : '–'}))}">${steps}</div>
      <p class="meta">${esc(t('cp_level_path', {a: cur ? cur.code : '–', b: target ? target.code : '–'}))}</p>`;
  }

  function coursesHtml(courses) {
    if (!courses.length) return App.emptyHtml(t('cp_no_courses'));
    return `<ul class="plain">${courses.map(k => `<li>${can('schedule.view') ? `<a href="/courses/${k.id}">${esc(k.name)}</a>` : esc(k.name)}
      <span class="meta">${esc(k.instructor ? k.instructor.name : t('co_no_instructor'))} · ${esc(t('cs_' + k.status))}</span></li>`).join('')}</ul>`;
  }

  function attendanceHtml(att) {
    const s = att.stats;
    if (!s.recorded) return App.emptyHtml(t('at_none_yet'));
    return `<p><span class="big-rate">${esc(t('at_rate_line', {r: AttendanceForm.rateText(s.rate)}))}</span>
      <span class="meta">${esc(AttendanceForm.countsText(s))}</span></p>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_date'))}</th><th>${esc(t('f_course'))}</th>
      <th>${esc(t('f_status'))}</th><th>${esc(t('at_note'))}</th></tr></thead><tbody>
      ${att.recent.map(a => `<tr><td class="nw">${esc(App.fmtSlot(a.session.date, a.session.start, a.session.end))}</td>
        <td>${esc(a.session.course.name)}</td><td>${AttendanceForm.statusBadge(a.status)}${a.minutes_late ? ` <span class="meta">${esc(t('at_minutes', {n: a.minutes_late}))}</span>` : ''}</td>
        <td>${esc(a.note || '–')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function ratingsHtml(ratings) {
    if (!ratings.length) return App.emptyHtml(t('cp_no_ratings'));
    const cats = ['r_practical', 'r_reliability', 'r_motivation'];
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_date'))}</th><th>${esc(t('rt_kind'))}</th><th>${esc(t('th_rater'))}</th>
      ${cats.map(c => `<th class="c">${esc(t('rt_cat_' + c))}</th>`).join('')}<th>${esc(t('f_note'))}</th></tr></thead>
      <tbody>${ratings.map(r => `<tr><td class="nw">${esc(fmtDateTime(r.created_at))}</td><td>${esc(t('rt_kind_' + r.kind))}</td>
        <td>${esc(r.rater || '–')}</td>${cats.map(c => `<td class="c">${esc(fmtNum(r[c]))}</td>`).join('')}
        <td class="wrap">${esc(r.note || '–')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function reportsHtml(training) {
    const rows = training.recent_reports;
    if (!rows.length) return App.emptyHtml(t('rp_empty'));
    const more = training.report_count > rows.length ? ' ' + t('cp_latest', {n: rows.length}) : '';
    return `<p class="meta">${esc(t('cp_hours', {h: fmtNum(training.hours_total), r: training.report_count}) + more)}</p>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('th_date'))}</th><th class="c">${esc(t('th_hours'))}</th>
      <th>${esc(t('th_area'))}</th><th>${esc(t('th_learned'))}</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td class="nw">${esc(fmtDate(r.period))}</td><td class="c">${esc(fmtNum(r.hours))}</td>
        <td>${esc([r.lang ? t('f_lang') : '', r.tech ? t('f_tech') : ''].filter(Boolean).join(', ') || '–')}</td>
        <td class="wrap">${esc(r.learned || '–')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function render() {
    const c = data.candidate;
    const archived = !!c.archived_at;
    document.title = `${c.name} · Azubi-Training`;
    const report = can('report.view') ? `<a class="btn ghost sm" href="/reports/candidates/${c.id}">${esc(t('rp_report_button'))}</a>` : '';
    const actions = can('candidate.edit') || report ? `<div class="tools">${report}
      ${archived || !can('candidate.edit') ? '' : `<button class="btn sm" type="button" data-action="edit">${esc(t('edit'))}</button>`}
      ${can('candidate.edit') ? `<button class="btn ${archived ? 'ghost' : 'danger'} sm" type="button" data-action="${archived ? 'restore' : 'archive'}">${esc(t(archived ? 'btn_restore' : 'btn_archive'))}</button>` : ''}</div>` : '';
    host.innerHTML = `
      <div class="card"><div class="profile-head"><div>
        <h2>${esc(c.name)}${c.nickname ? ` <span class="mut">(${esc(c.nickname)})</span>` : ''}</h2>
        <span class="badge">${esc(c.candidate_no)}</span> ${c.status ? `<span class="badge ok">${esc(c.status.name)}</span>` : ''}
        ${archived ? `<span class="badge warn">${esc(t('archived'))}</span>` : ''}
        <p class="meta">${esc(App.stamp('cp_created', c.created_at, c.created_by))}
          ${c.updated_at ? ' · ' + esc(App.stamp('cp_updated', c.updated_at, c.updated_by)) : ''}
          ${archived ? ' · ' + esc(App.stamp('cp_archived', c.archived_at, c.archived_by)) : ''}</p>
      </div>${actions}</div></div>
      <div class="profile-grid">
        <section class="card"><h3>${esc(t('cp_personal'))}</h3><dl class="facts">
          ${fact('f_email', c.email)}${fact('f_phone', c.phone)}${fact('f_birth', c.date_of_birth && fmtDate(c.date_of_birth))}${fact('f_login', c.msh_user)}
        </dl></section>
        <section class="card"><h3>${esc(t('cp_training_info'))}</h3><dl class="facts">
          ${fact('f_status', c.status && c.status.name)}${fact('f_program', c.program && c.program.name)}${fact('f_fach', c.fach)}${fact('f_target_occupation', c.target_occupation)}
          ${fact('f_department', c.department && c.department.name)}${fact('f_abteilung', c.abteilung)}${fact('ov_th_spv', c.supervisor)}${fact('f_start', c.start_date && fmtDate(c.start_date))}
          ${fact('f_end', c.expected_completion_date && fmtDate(c.expected_completion_date))}
        </dl></section>
        <section class="card"><h3>${esc(t('cp_language'))}</h3>${levelPath(c)}</section>
        <section class="card"><h3>${esc(t('nav_courses'))}</h3>${coursesHtml(data.courses)}</section>
        <section class="card"><h3>${esc(t('cp_next_sessions'))}</h3>${data.upcoming_sessions.length
          ? `<div class="sess-list">${data.upcoming_sessions.map(x => SessionForm.cardHtml(x, {showDate: true})).join('')}</div>`
          : App.emptyHtml(t('cp_no_sessions'))}</section>
      </div>
      <h2 class="section-title">${esc(t('pr_title'))}</h2><div id="progress-host"></div>
      ${data.attendance ? `<section class="card section-gap" data-attendance><h3>${esc(t('at_section'))}</h3>${attendanceHtml(data.attendance)}</section>` : ''}
      ${data.assessments ? `<section class="card section-gap"><div class="pghead"><h3>${esc(t('as_section'))}</h3>
        ${can('assessment.create') && !archived ? `<div class="tools"><button class="btn sm" type="button" data-action="newAssessment">${esc(t('as_new'))}</button></div>` : ''}</div>
        ${AssessmentForm.historyHtml(data.assessments)}</section>` : ''}
      ${data.lesson_ratings ? `<section class="card section-gap"><h3>${esc(t('cp_lesson_ratings'))}</h3>
        ${LessonView.historyHtml(data.lesson_ratings.ratings, data.lesson_ratings.rules)}</section>` : ''}
      ${data.ratings ? `<section class="card section-gap"><h3>${esc(t('cp_ratings'))}</h3>${ratingsHtml(data.ratings)}</section>` : ''}
      <section class="card section-gap"><h3>${esc(t('cp_reports'))}</h3>${reportsHtml(data.training)}</section>
      ${can('audit.view') ? `<section class="card section-gap" data-history><h3>${esc(t('cp_history'))}</h3>${App.loadingHtml()}</section>` : ''}`;
    ProgressView.render($('#progress-host'), progress, {withAttendance: false});
    loadHistory();
    const att = host.querySelector('[data-attendance]');
    if (att && progress.attendance && data.attendance.stats.recorded) ProgressView.attendanceChart(att, progress.attendance);
  }

  /* Change history (super admin only): the last 50 entries for this candidate. */
  async function loadHistory() {
    const box = host.querySelector('[data-history]');
    if (!box) return;
    try {
      const body = await api('GET', `/api/activity?entity_type=trainee&entity_id=${id}&limit=50`);
      box.innerHTML = `<h3>${esc(t('cp_history'))}</h3>${body.activity.length ? ActivityList.tableHtml(body.activity, {showEntity: false})
        : App.emptyHtml(t('vl_empty'))}${body.next_before_id ? `<a class="btn ghost sm" href="/activity?entity_type=trainee&q=${encodeURIComponent(data.candidate.name)}">${esc(t('vl_more'))}</a>` : ''}`;
    } catch (err) { App.showError(box, err); }
  }

  App.onActions(host, {
    session: sid => SessionForm.show(data.upcoming_sessions.find(x => x.id === sid), {onChanged: load}),
    edit: () => CandidateForm.open(data.candidate, load),
    newAssessment: () => AssessmentForm.create({trainee: {...data.candidate, courses: data.courses}}),
    archive: async () => {
      if (!await App.confirmDialog(t('confirm_archive', {name: data.candidate.name}))) return;
      try { await api('POST', `/api/candidates/${id}/archive`); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
    },
    restore: async () => {
      try { await api('POST', `/api/candidates/${id}/restore`); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
    },
  });
  App.onRerender(() => data && render());
  load();
})();

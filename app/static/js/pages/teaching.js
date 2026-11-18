/* Instructor: "Mein Unterricht" (my teaching) — today's + upcoming sessions, metrics, own courses, participants. */
(() => {
  const {$, esc, t, api, fmtNum} = App;
  const host = $('#page');
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', '/api/my-teaching');
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  const tile = (value, label) => `<div class="stat"><b>${esc(value)}</b><span>${esc(t(label))}</span></div>`;

  const sessionsHtml = (list, showDate, emptyText) => (list.length
    ? `<div class="sess-list">${list.map(x => SessionForm.cardHtml(x, {showDate})).join('')}</div>` : App.emptyHtml(emptyText));

  /* Open module ratings: straight into the capture form (Panduan: fill out the same day). */
  const lessonsHtml = () => `<ul class="plain">${data.open_lesson_ratings.map(x => `<li><a href="/sessions/${x.id}/lesson">${esc(x.course.name)}</a>
    · ${esc(x.module ? x.module.name : '')} ${esc(LessonView.unitText(x.unit))} · ${esc(App.fmtSlot(x.date, x.start, x.end))}</li>`).join('')}</ul>`;

  function coursesHtml() {
    if (!data.courses.length) return App.emptyHtml(t('te_no_courses'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_name'))}</th><th>${esc(t('th_level'))}</th>
      <th>${esc(t('f_current_module'))}</th><th class="c">${esc(t('th_participants'))}</th><th>${esc(t('f_status'))}</th></tr></thead>
      <tbody>${data.courses.map(c => `<tr><td class="name"><a href="/courses/${c.id}">${esc(c.name)}</a></td>
        <td class="nw"><span class="badge">${esc(c.level.code)}</span></td>
        <td>${c.module ? `<a href="/modules/${c.module.id}">${esc(c.module.name)}</a>` : '–'}</td>
        <td class="c">${c.participant_count}</td><td>${CourseForm.statusBadge(c.status)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function participantsHtml() {
    if (!data.participants.length) return App.emptyHtml(t('te_no_participants'));
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_name'))}</th><th>${esc(t('f_candidate_no'))}</th>
      <th>${esc(t('th_level'))}</th><th>${esc(t('f_status'))}</th><th>${esc(t('nav_courses'))}</th><th></th></tr></thead>
      <tbody>${data.participants.map(p => `<tr><td class="name"><a href="/candidates/${p.id}">${esc(p.name)}</a>
        ${p.nickname ? ` <span class="mut">(${esc(p.nickname)})</span>` : ''}</td><td class="nw">${esc(p.candidate_no)}</td>
        <td class="nw">${p.current_level ? `<span class="badge">${esc(p.current_level.code)}</span>` : '–'}</td>
        <td>${p.status ? esc(p.status.name) : '–'}</td><td>${p.courses.map(c => esc(c.name)).join(', ')}</td>
        <td><button class="btn ghost sm" type="button" data-action="assess" data-id="${p.id}">${esc(t('te_assess'))}</button></td></tr>`).join('')}
      </tbody></table></div>`;
  }

  function render() {
    const i = data.instructor, s = data.stats;
    host.innerHTML = `
      <div class="card hero"><h2>${esc(t('te_hello', {name: i.name}))}</h2>
        <p>${esc(t('te_intro'))}</p>
        ${i.levels.map(l => `<span class="badge">${esc(l.name)}</span>`).join('')}
        <p class="meta">${esc(t('f_availability'))}: ${esc(InstructorForm.weekText(i.availability))}</p></div>
      <div class="stats">${tile(s.open_lesson_count, 'te_open_lessons')}${tile(s.open_attendance_count, 'te_open_attendance')}${tile(s.open_assessment_count, 'te_open_assessments')}${tile(s.today_count, 'te_today_count')}${tile(fmtNum(s.hours_month), 'te_hours_month')}
        ${tile(s.course_count, 'te_courses')}${tile(s.participant_count, 'th_participants')}</div>
      ${data.open_lesson_ratings.length ? `<section class="card"><h3>${esc(t('te_open_lessons_title'))}</h3>
        <p class="meta">${esc(t('te_open_lessons_hint', {n: data.windows.open_lesson_days}))}</p>${lessonsHtml()}</section>` : ''}
      ${data.open_attendance.length ? `<section class="card"><h3>${esc(t('te_open_attendance_title'))}</h3>
        <p class="meta">${esc(t('te_open_attendance_hint', {n: data.windows.open_attendance_days}))}</p>${sessionsHtml(data.open_attendance, true, '')}</section>` : ''}
      ${data.open_assessments.length ? `<section class="card"><h3>${esc(t('te_open_assessments_title'))}</h3>
        <p class="meta">${esc(t('te_open_assessments_hint'))}</p>${AssessmentForm.historyHtml(data.open_assessments, {showTrainee: true})}</section>` : ''}
      <section class="card"><h3>${esc(t('te_today'))}</h3>${sessionsHtml(data.today, false, t('te_no_today'))}</section>
      <section class="card"><h3>${esc(t('te_upcoming', {n: data.windows.upcoming_days}))}</h3>${sessionsHtml(data.upcoming, true,
        t('te_no_upcoming', {n: data.windows.upcoming_days}))}</section>
      <section class="card"><h3>${esc(t('te_my_courses'))}</h3>${coursesHtml()}</section>
      <section class="card"><h3>${esc(t('te_my_participants'))}</h3>${participantsHtml()}</section>`;
  }

  App.onActions(host, {
    assess: tid => AssessmentForm.create({trainee: data.participants.find(p => p.id === tid)}),
    session: id => SessionForm.show([...data.open_attendance, ...data.today, ...data.upcoming].find(x => x.id === id),
                                    {onChanged: load}),
  });
  App.onRerender(() => data && render());
  load();
})();

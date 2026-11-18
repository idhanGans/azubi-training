/* Kandidatenbericht (druckbar): Stammdaten, Niveau, Kurse, Anwesenheit, Fertigkeiten, Module, Bewertungen, Feedback.
   Ohne interne Notizen — darf an den Kandidaten weitergegeben werden. */
(() => {
  const {$, esc, t, api, fmtDate, fmtNum} = App;
  const host = $('#page');
  const id = +host.dataset.candidateId;
  const params = new URLSearchParams(location.search);
  const range = {from: params.get('from') || '', to: params.get('to') || ''};
  const FEEDBACK = ['strengths', 'improvements', 'recommendations', 'general_feedback'];
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    const p = new URLSearchParams();
    if (range.from) p.set('from', range.from);
    if (range.to) p.set('to', range.to);
    history.replaceState(null, '', location.pathname + (p.toString() ? `?${p}` : ''));
    try {
      data = await api('GET', `/api/reports/candidates/${id}?${p}`);
      render();
    } catch (err) {
      App.showError(host, err, err.status === 404 ? null : load);
    }
  }

  const pct = v => (v == null ? '–' : `${fmtNum(v, 1)} %`);
  const facts = rows => `<dl class="facts">${rows.map(([k, v]) => `<dt>${esc(t(k))}</dt><dd>${v == null || v === '' ? '–' : esc(v)}</dd>`).join('')}</dl>`;

  function attendanceHtml(a) {
    const line = s => (s && s.recorded ? `${AttendanceForm.rateText(s.rate)} · ${AttendanceForm.countsText(s)}` : t('at_none_yet'));
    return facts([['rp_in_period', line(a.period)], ['rp_overall', line(a.total)]]);
  }

  function render() {
    const c = data.candidate, p = data.period;
    App.setPageTitle(t('rp_candidate_title', {name: c.name}), [{href: '/reports?tab=candidate', label: t('nav_reports')}]);
    host.innerHTML = `<div class="card no-print filters">
        <label class="meta">${esc(t('rp_from'))}<input class="input" type="date" name="from" value="${esc(p.from)}"></label>
        <label class="meta">${esc(t('rp_to'))}<input class="input" type="date" name="to" value="${esc(p.to)}"></label>
        <button class="btn ghost sm" type="button" data-all>${esc(t('rp_whole_history'))}</button>
        <button class="btn sm" type="button" data-print>${esc(t('rp_print'))}</button>
        <a class="btn ghost sm" href="/candidates/${c.id}">${esc(t('rp_to_profile'))}</a></div>
      <div class="card report-head"><h2>${esc(c.name)} <span class="mut">${esc(c.candidate_no)}</span></h2>
        <p class="meta">${esc(t('rp_candidate_period', {a: fmtDate(p.from), b: fmtDate(p.to)}))} · ${esc(t('rp_no_internal'))}</p></div>
      <div class="profile-grid">
        <section class="card"><h3>${esc(t('cp_personal'))}</h3>${facts([['f_email', c.email], ['f_phone', c.phone],
          ['f_abteilung', c.abteilung], ['f_fach', c.fach], ['f_status', c.status && c.status.name]])}</section>
        <section class="card"><h3>${esc(t('cp_language'))}</h3>${facts([['mp_current_level', c.current_level && c.current_level.name],
          ['mp_target_level', c.target_level && c.target_level.name], ['f_program', c.program && c.program.name],
          ['nav_courses', c.courses.map(k => k.name).join(', ')]])}</section>
        <section class="card"><h3>${esc(t('at_section'))}</h3>${attendanceHtml(data.attendance)}</section>
      </div>
      <section class="card section-gap"><h3>${esc(t('pr_skills'))}</h3>${data.progress.skills.length
        ? `<ul class="skill-bars">${data.progress.skills.map(s => `<li><span>${esc(t('sk_' + s.skill))}</span>
          <span class="bar" aria-hidden="true"><i style="width:${Math.max(0, Math.min(100, s.current))}%"></i></span><b>${esc(pct(s.current))}</b></li>`).join('')}</ul>`
        : App.emptyHtml(t('pr_no_skills'))}</section>
      <section class="card section-gap"><h3>${esc(t('pr_modules'))}</h3>${data.progress.modules.length ? data.progress.modules.map(m => `
        <p><b>${esc(m.curriculum.program)} · ${esc(m.curriculum.level.code)}</b> — ${esc(t('pr_modules_done', {c: m.completed, n: m.total, p: pct(m.percent)}))}
        ${m.current ? ' · ' + esc(t('pr_current', {m: m.current.name})) : ''}</p>`).join('') : App.emptyHtml(t('pr_no_modules'))}</section>
      <section class="card section-gap"><h3>${esc(t('rp_assessments'))}</h3>${data.assessments.length ? `<div class="tbl-wrap"><table class="tbl">
        <thead><tr><th>${esc(t('f_date'))}</th><th>${esc(t('as_template'))}</th><th>${esc(t('as_examiner'))}</th>
          <th>${esc(t('as_category'))}</th><th class="c">${esc(t('as_result'))}</th><th>${esc(t('f_status'))}</th></tr></thead>
        <tbody>${data.assessments.map(a => `<tr><td class="nw">${esc(fmtDate(a.assessed_on))}</td><td>${esc(a.template.name)}</td>
          <td>${esc(a.instructor.name)}</td><td>${a.categories.map(cat => `${esc(cat.name)} ${esc(pct(cat.percent))}`).join('<br>')}</td>
          <td class="c"><b>${esc(pct(a.overall_percent))}</b></td><td>${AssessmentForm.passBadge(a.passed)}</td></tr>`).join('')}</tbody></table></div>`
        : App.emptyHtml(t('rpt_empty'))}</section>
      <section class="card section-gap"><h3>${esc(t('rp_feedback'))}</h3>${data.feedback.length ? data.feedback.map(f => `
        <div class="report-feedback"><p class="meta">${esc(fmtDate(f.date))} · ${esc(f.template)}</p>
        <div class="feedback-grid">${FEEDBACK.filter(k => f[k]).map(k => `<div><h4>${esc(t('as_f_' + k))}</h4><p class="wrap-text">${esc(f[k])}</p></div>`).join('')}</div></div>`).join('')
        : App.emptyHtml(t('fb_none'))}</section>`;
  }

  host.addEventListener('change', ev => {
    if (ev.target.name === 'from' || ev.target.name === 'to') { range[ev.target.name] = ev.target.value; load(); }
  });
  host.addEventListener('click', ev => {
    if (ev.target.closest('[data-print]')) window.print();
    if (ev.target.closest('[data-all]')) { range.from = ''; range.to = ''; load(); }
  });
  App.onRerender(() => data && render());
  load();
})();

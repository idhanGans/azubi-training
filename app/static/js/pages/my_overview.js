/* Kandidat: Übersicht — Begruessung, Heute (Unterricht + Tages-Report), Kennzahlen, naechste Termine,
   neueste Rueckmeldung, Fertigkeiten. */
(() => {
  const {$, esc, t, api, fmtDate, fmtNum} = App;
  const host = $('#page');
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', '/api/my-overview');
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  const pct = v => (v == null ? '–' : `${fmtNum(v, 1)} %`);

  function feedbackHtml(a) {
    if (!a) return App.emptyHtml(t('as_none_own'));
    const text = a.recommendations || a.general_feedback || a.improvements || a.strengths;
    return `<p><b>${esc(a.template.name)}</b> · ${esc(fmtDate(a.assessed_on))} · ${esc(pct(a.overall_percent))}
      ${AssessmentBadge(a.passed)}</p>
      ${text ? `<blockquote class="quote">${esc(text)}</blockquote>` : ''}
      <a class="btn ghost sm" href="/my-feedback">${esc(t('ov_all_feedback'))}</a>`;
  }

  const AssessmentBadge = passed => (passed == null ? ''
    : `<span class="badge ${passed ? 'ok' : 'warn'}">${esc(t(passed ? 'as_passed' : 'as_failed'))}</span>`);

  /* „Was muss ich heute tun?" — Unterricht heute und der Tages-Report (beides vom Server). */
  function todayHtml(d) {
    const day = App.days.label(d.date, {weekday: 'long', day: '2-digit', month: '2-digit'});
    /* Report fehlt: Formular direkt hier (wie im alten Trainings-Monitoring), Verlauf auf „Mein Trainings-Report". */
    const report = d.report_done
      ? `<p class="today-report done">${App.icon('check-circle')} ${esc(t('ov_report_done'))}</p>`
      : `<p class="today-report">${esc(t('ov_report_open'))}</p>${ReportForm.html(null)}`;
    return `<section class="card"><h3>${esc(t('ov_today', {d: day}))}</h3>
      ${d.sessions.length ? `<ul class="plain">${d.sessions.map(s => Portal.sessionHtml(s)).join('')}</ul>`
        : `<p class="meta">${esc(t('ov_today_no_class'))}</p>`}
      ${report}
      <div class="form-actions"><a class="btn ghost sm" href="/my-reports">${esc(t('ov_reports_all'))}</a></div></section>`;
  }

  async function submitReport(ev) {
    ev.preventDefault();
    if (!await ReportForm.submit(ev.target)) return;
    App.toast(t('saved'));
    await load();
  }

  function render() {
    const c = data.candidate, next = data.next_sessions[0], m = data.modules[0], a = data.latest_assessment;
    const levels = [c.current_level && c.current_level.code, c.target_level && c.target_level.code];
    host.innerHTML = `
      <div class="card hero"><h2>${esc(t('c_hi', {name: c.nickname || c.name}))}</h2>
        <p>${esc(t('ov_intro'))}</p>
        ${c.status ? `<span class="badge">${esc(c.status.name)}</span>` : ''}
        ${levels[0] || levels[1] ? `<span class="badge">${esc(t('ov_level', {a: levels[0] || '–', b: levels[1] || '–'}))}</span>` : ''}
        <span class="badge">${esc(c.candidate_no)}</span></div>
      ${todayHtml(data.today)}
      <div class="stats">
        ${Portal.tile(next ? `${App.days.label(next.date, {weekday: 'short', day: '2-digit', month: '2-digit'})} ${next.start}` : '–', 'ov_next', '/my-schedule', true)}
        ${Portal.tile(data.attendance.rate == null ? '–' : `${fmtNum(data.attendance.rate * 100, 0)} %`, 'at_rate', '/my-attendance')}
        ${Portal.tile(a ? pct(a.overall_percent) : '–', 'ov_last_assessment', '/my-assessments')}
        ${Portal.tile(m ? `${m.completed}/${m.total}` : '–', 'ov_modules', '/my-modules')}
      </div>
      <section class="card"><h3>${esc(t('ov_next_sessions'))}</h3>${data.next_sessions.length
        ? `<ul class="plain">${data.next_sessions.map(s => Portal.sessionHtml(s, {showDate: true})).join('')}</ul>`
        : App.emptyHtml(t('ms_empty'))}</section>
      <section class="card"><h3>${esc(t('ov_latest_feedback'))}</h3>${feedbackHtml(a)}</section>
      ${m ? `<section class="card"><h3>${esc(t('ov_current_module'))}</h3>
        <p><b>${esc(m.current ? m.current.name : t('pr_state_done'))}</b></p>
        <p class="meta">${esc(t('pr_modules_done', {c: m.completed, n: m.total, p: pct(m.percent)}))}</p>
        <a class="btn ghost sm" href="/my-modules">${esc(t('ov_to_modules'))}</a></section>` : ''}
      ${data.skills.length ? `<section class="card"><h3>${esc(t('pr_skills'))}</h3><ul class="skill-bars">
        ${data.skills.map(s => `<li><span>${esc(t('sk_' + s.skill))}</span>
          <span class="bar" role="img" aria-label="${esc(t('sk_' + s.skill))}: ${esc(pct(s.current))}"><i style="width:${Math.max(0, Math.min(100, s.current))}%"></i></span>
          <b>${esc(pct(s.current))}</b></li>`).join('')}</ul>
        <a class="btn ghost sm" href="/my-progress">${esc(t('ov_to_progress'))}</a></section>` : ''}`;
    const form = $('#report-form');
    if (form) form.addEventListener('submit', submitReport);
  }

  App.onRerender(() => data && render());
  load();
})();

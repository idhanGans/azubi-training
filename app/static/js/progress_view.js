/* Fortschritts-Ansicht (Kandidatenprofil + „Mein Fortschritt"): Fertigkeiten als kleine Einzel-Diagramme,
   Verlauf der Gesamtergebnisse, Module, Anwesenheit je Woche. Werte kommen fertig vom Server
   (app/services/progress.py) — hier wird nur dargestellt. */
const ProgressView = (() => {
  const {esc, t, fmtDate, fmtNum} = App;
  const {pct} = Charts;
  const shortDate = iso => App.days.label(iso, {day: '2-digit', month: '2-digit'});

  function delta(skill) {
    if (skill.count < 2) return `<span class="meta">${esc(t('pr_first_only'))}</span>`;
    const d = skill.change;
    if (!d) return `<span class="meta">±0 ${esc(t('pr_since', {d: fmtDate(skill.series[0].date)}))}</span>`;
    return `<span class="delta ${d > 0 ? 'up' : 'down'}">${d > 0 ? '▲ +' : '▼ −'}${esc(fmtNum(Math.abs(d), 1))}</span>
      <span class="meta">${esc(t('pr_since', {d: fmtDate(skill.series[0].date)}))}</span>`;
  }

  function skillsSection(host, body) {
    const card = document.createElement('section');
    card.className = 'card';
    card.innerHTML = `<h3>${esc(t('pr_skills'))}</h3><p class="meta">${esc(t('pr_skills_hint'))}</p>`;
    host.appendChild(card);
    if (!body.skills.length) { card.insertAdjacentHTML('beforeend', App.emptyHtml(t('pr_no_skills'))); return; }
    const grid = document.createElement('div');
    grid.className = 'skill-grid';
    card.appendChild(grid);
    body.skills.forEach(s => {
      const tile = document.createElement('div');
      tile.className = 'skill-tile';
      tile.innerHTML = `<div class="skill-head"><span>${esc(t('sk_' + s.skill))}</span><b>${esc(pct(s.current))}</b></div>
        <div class="skill-delta">${delta(s)}</div>`;
      grid.appendChild(tile);
      Charts.line(tile, {
        width: 300, height: 130,
        points: s.series.map(p => ({value: p.percent, time: Date.parse(p.date), short: shortDate(p.date), valueText: pct(p.percent),
                                    label: `${p.template} · ${fmtDate(p.date)}`})),
        table: {head: [t('f_date'), t('as_template'), t('sk_' + s.skill)],
                rows: s.series.map(p => [fmtDate(p.date), p.template, pct(p.percent)])},
      });
    });
  }

  function trendSection(host, body) {
    if (!body.assessment_trend.length) return;
    const card = document.createElement('section');
    card.className = 'card';
    host.appendChild(card);
    Charts.line(card, {
      title: t('pr_trend'), caption: t('pr_trend_hint'),
      points: body.assessment_trend.map(p => ({value: p.overall_percent, time: Date.parse(p.date), short: shortDate(p.date),
        valueText: pct(p.overall_percent),
        label: `${p.template} · ${fmtDate(p.date)} · ${t(p.passed ? 'as_passed' : 'as_failed')}`})),
      table: {head: [t('f_date'), t('as_template'), t('as_result'), t('f_status')],
              rows: body.assessment_trend.map(p => [fmtDate(p.date), p.template, pct(p.overall_percent),
                                                    t(p.passed ? 'as_passed' : 'as_failed')])},
    });
  }

  const STATE_ICON = {done: 'check', current: 'circle-dot', open: 'circle'};

  function modulesSection(host, body) {
    const card = document.createElement('section');
    card.className = 'card';
    card.innerHTML = `<h3>${esc(t('pr_modules'))}</h3>${body.modules.length ? '' : App.emptyHtml(t('pr_no_modules'))}
      ${body.modules.map(m => `<div class="module-progress">
        <p><b>${esc(m.curriculum.program)} · ${esc(m.curriculum.level.code)}</b> <span class="meta">${esc(m.course.name)}</span></p>
        ${Charts.meter(m.percent, t('pr_modules_done', {c: m.completed, n: m.total, p: pct(m.percent)}))}
        <p class="meta">${esc(t('pr_modules_done', {c: m.completed, n: m.total, p: pct(m.percent)}))}${m.current
          ? ' · ' + esc(t('pr_current', {m: m.current.name})) : ''}</p>
        <details><summary>${esc(t('pr_module_list'))}</summary><ol class="module-steps">
          ${m.items.map(i => `<li class="${i.state}">${App.icon(STATE_ICON[i.state], 'mstate ' + i.state)} ${esc(i.name)}
            <span class="sr-only">(${esc(t('pr_state_' + i.state))})</span>${i.state === 'current' ? ` <span class="badge">${esc(t('pr_state_current'))}</span>` : ''}</li>`).join('')}
        </ol></details></div>`).join('')}`;
    host.appendChild(card);
  }

  function attendanceSection(host, body) {
    const att = body.attendance;
    const card = document.createElement('section');
    card.className = 'card';
    card.innerHTML = `<h3>${esc(t('at_section'))}</h3>`;
    host.appendChild(card);
    if (!att.stats.recorded) { card.insertAdjacentHTML('beforeend', App.emptyHtml(t('at_none_yet'))); return; }
    card.insertAdjacentHTML('beforeend', `<p><span class="big-rate">${esc(t('at_rate_line', {r: AttendanceForm.rateText(att.stats.rate)}))}</span>
      <span class="meta">${esc(AttendanceForm.countsText(att.stats))}</span></p>`);
    attendanceChart(card, att);
  }

  /* Anwesenheitsquote je Woche (auch einzeln fuer den Anwesenheits-Abschnitt im Profil). */
  function attendanceChart(card, att) {
    if (!att.weeks.length) return;
    const counts = w => t('at_counts', {p: w.present, l: w.late, e: w.excused, a: w.absent});
    Charts.columns(card, {
      title: t('pr_att_weeks'), caption: t('at_rule'),
      points: att.weeks.map(w => ({value: w.rate == null ? null : w.rate * 100, short: shortDate(w.week_start),
        valueText: w.rate == null ? '–' : pct(w.rate * 100), label: `${t('pr_week_of', {d: fmtDate(w.week_start)})} · ${counts(w)}`})),
      table: {head: [t('pr_week'), t('at_rate'), t('at_PRESENT'), t('at_LATE'), t('at_EXCUSED'), t('at_ABSENT')],
              rows: att.weeks.map(w => [fmtDate(w.week_start), w.rate == null ? '–' : pct(w.rate * 100),
                                        w.present, w.late, w.excused, w.absent])},
    });
  }

  /* withAttendance=false: das Profil hat schon einen eigenen Anwesenheits-Abschnitt. */
  function render(host, body, {withAttendance = true} = {}) {
    host.innerHTML = '';
    if (body.skills) skillsSection(host, body);
    if (body.assessment_trend) trendSection(host, body);
    modulesSection(host, body);
    if (body.attendance && withAttendance) attendanceSection(host, body);
  }

  return {render, attendanceChart};
})();

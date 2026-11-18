/* Team-Übersicht: Kennzahlen, Verteilung nach Status/Niveau, Handlungsbedarf (nur was die Rolle erledigen darf).
   Zahlen kommen fertig vom Server (app/services/dashboard.py). */
(() => {
  const {$, esc, t, api, fmtNum, fmtDate, fmtTimeRange} = App;
  const host = $('#page');
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', '/api/dashboard');
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  const pct = v => (v == null ? '–' : `${fmtNum(v, 1)} %`);

  function tile(value, key, hint, href) {
    const inner = `<b>${esc(value)}</b><span>${esc(t(key))}</span><small class="meta">${esc(hint)}</small>`;
    return href ? `<a class="stat link-stat" href="${esc(href)}">${inner}</a>` : `<div class="stat">${inner}</div>`;
  }

  function bars(rows, emptyKey) {
    if (!rows.length) return App.emptyHtml(t(emptyKey));
    const max = Math.max(...rows.map(r => r.count));
    return `<ul class="count-bars">${rows.map(r => `<li><span>${esc(r.label || t('db_not_set'))}</span>
      <span class="bar" aria-hidden="true"><i style="width:${(r.count / max) * 100}%"></i></span><b>${r.count}</b></li>`).join('')}</ul>`;
  }

  const person = p => `<a href="/candidates/${p.id}">${esc(p.name)}</a> <span class="meta">${esc(p.candidate_no)}</span>`;
  const more = (block, shown) => (block.count > shown ? `<p class="meta">${esc(t('db_more', {n: block.count - shown}))}</p>` : '');

  function attentionHtml(a) {
    const cards = [];
    if (a.open_assessments) {
      cards.push(`<div class="todo"><b>${a.open_assessments.count}</b> ${esc(t('db_open_assessments'))}
        ${a.open_assessments.count ? `<a class="btn ghost sm" href="/assessments?status=DRAFT">${esc(t('db_show'))}</a>` : ''}</div>`);
    }
    if (a.open_attendance) {
      cards.push(`<div class="todo"><b>${a.open_attendance.count}</b> ${esc(t('db_open_attendance', {n: a.open_attendance.days}))}
        ${a.open_attendance.items.length ? `<ul class="plain">${a.open_attendance.items.map(s => `<li>${esc(fmtDate(s.date))}
          ${esc(fmtTimeRange(s.start, s.end))} · <a href="/schedule?view=day&date=${esc(s.date)}">${esc(s.course.name)}</a></li>`).join('')}</ul>` : ''}
        ${more(a.open_attendance, a.open_attendance.items.length)}</div>`);
    }
    if (a.open_lesson_ratings) {
      cards.push(`<div class="todo"><b>${a.open_lesson_ratings.count}</b> ${esc(t('db_open_lessons', {n: a.open_lesson_ratings.days}))}
        ${a.open_lesson_ratings.items.length ? `<ul class="plain">${a.open_lesson_ratings.items.map(s => `<li>${esc(fmtDate(s.date))}
          · <a href="/sessions/${s.id}/lesson">${esc(s.course.name)}</a> <span class="meta">${esc(s.module ? s.module.name : '')}</span></li>`).join('')}</ul>` : ''}
        ${more(a.open_lesson_ratings, a.open_lesson_ratings.items.length)}</div>`);
    }
    if (a.lesson_coaching) {
      cards.push(`<div class="todo"><b>${a.lesson_coaching.count}</b> ${esc(t('db_lesson_coaching'))}
        ${a.lesson_coaching.items.length ? `<ul class="plain">${a.lesson_coaching.items.map(p => `<li>${person(p)}
          <span class="meta">${esc(fmtDate(p.date))}</span></li>`).join('')}</ul>` : ''}${more(a.lesson_coaching, a.lesson_coaching.items.length)}
        ${a.lesson_coaching.count ? `<a class="btn ghost sm" href="/lesson-reports">${esc(t('nav_lesson_reports'))}</a>` : ''}</div>`);
    }
    if (a.low_attendance) {
      cards.push(`<div class="todo"><b>${a.low_attendance.count}</b> ${esc(t('db_low_attendance', {p: a.low_attendance.below_percent}))}
        ${a.low_attendance.items.length ? `<ul class="plain">${a.low_attendance.items.map(p => `<li>${person(p)}
          <span class="badge warn">${esc(pct(p.rate * 100))}</span></li>`).join('')}</ul>` : ''}${more(a.low_attendance, a.low_attendance.items.length)}</div>`);
    }
    if (a.without_course) {
      cards.push(`<div class="todo"><b>${a.without_course.count}</b> ${esc(t('db_without_course'))}
        ${a.without_course.items.length ? `<ul class="plain">${a.without_course.items.map(p => `<li>${person(p)}</li>`).join('')}</ul>` : ''}
        ${more(a.without_course, a.without_course.items.length)}
        ${a.without_course.count ? `<a class="btn ghost sm" href="/courses">${esc(t('db_to_courses'))}</a>` : ''}</div>`);
    }
    if (a.incomplete_profile) {
      cards.push(`<div class="todo"><b>${a.incomplete_profile.count}</b> ${esc(t('db_incomplete'))}
        ${a.incomplete_profile.items.length ? `<ul class="plain">${a.incomplete_profile.items.map(p => `<li>${person(p)}
          <span class="meta">${esc(t('db_missing', {f: p.missing.map(f => t('db_f_' + f)).join(', ')}))}</span></li>`).join('')}</ul>` : ''}
        ${more(a.incomplete_profile, a.incomplete_profile.items.length)}</div>`);
    }
    return cards.length ? `<div class="todo-grid">${cards.join('')}</div>` : App.emptyHtml(t('db_nothing'));
  }

  function render() {
    const k = data.kpis;
    host.innerHTML = `<p class="hint">${esc(t(data.scope === 'all' ? 'db_scope_all' : 'db_scope_own'))}</p>
      <div class="stats kpis">
        ${tile(k.candidates, 'db_candidates', t('db_candidates_hint'), '/candidates')}
        ${tile(k.active_candidates, 'db_active', t('db_active_hint'))}
        ${tile(pct(k.avg_assessment), 'db_avg_assessment', t('db_avg_assessment_hint', {n: k.assessed_candidates}), '/assessments')}
        ${tile(k.attendance ? pct(k.attendance.rate == null ? null : k.attendance.rate * 100) : '–', 'db_attendance', t('db_attendance_hint'))}
        ${tile(pct(k.modules_completed), 'db_modules', t('db_modules_hint', {c: k.modules.completed, n: k.modules.total}))}
        ${tile(k.open_assessments, 'db_open_assessments', t('db_open_assessments_hint'), '/assessments?status=DRAFT')}
      </div>
      <section class="card"><h3>${esc(t('db_attention'))}</h3>${attentionHtml(data.attention)}</section>
      <div class="profile-grid">
        <section class="card"><h3>${esc(t('db_by_status'))}</h3>${bars(data.by_status, 'db_no_candidates')}</section>
        <section class="card"><h3>${esc(t('db_by_level'))}</h3>${bars(data.by_level, 'db_no_candidates')}</section>
      </div>`;
  }

  App.onRerender(() => data && render());
  load();
})();

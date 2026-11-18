/* Kandidat: eigene abgeschlossene Bewertungen — Ergebnis, Fertigkeiten, Feedback (neueste zuerst). */
(() => {
  const {$, esc, t, api, fmtDate} = App;
  const {pct, passBadge, delta} = AssessmentForm;
  const host = $('#page');
  const FEEDBACK = ['strengths', 'improvements', 'recommendations', 'general_feedback'];
  let data = null, lessons = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      [data, lessons] = await Promise.all([api('GET', '/api/my-assessments'), api('GET', '/api/my-lesson-ratings')]);
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function cardHtml(a, prev) {
    const feedback = FEEDBACK.filter(f => a[f]);
    return `<section class="card my-assessment"><div class="pghead"><h3>${esc(a.template.name)}</h3>${passBadge(a.passed)}</div>
      <p class="meta">${esc(fmtDate(a.assessed_on))} · ${esc(a.instructor.name)}${a.course ? ' · ' + esc(a.course.name) : ''}</p>
      <p class="big-rate">${esc(pct(a.overall_percent))} ${delta(a.overall_percent, prev)}</p>
      <ul class="skill-bars">${a.categories.map(c => `<li><span>${esc(c.name)}</span>
        <span class="bar" role="img" aria-label="${esc(c.name)}: ${esc(pct(c.percent))}"><i style="width:${Math.max(0, Math.min(100, c.percent || 0))}%"></i></span>
        <b>${esc(pct(c.percent))}</b></li>`).join('')}</ul>
      ${feedback.length ? `<div class="feedback-grid">${feedback.map(f => `<div><h4>${esc(t('as_f_' + f))}</h4>
        <p class="wrap-text">${esc(a[f])}</p></div>`).join('')}</div>` : ''}</section>`;
  }

  /* Modul-Bewertung: neueste Rueckmeldung gross (Level, Sterne, Staerke + Ziel), darunter der Verlauf. */
  function lessonsHtml() {
    const list = lessons.ratings, rules = lessons.rules;
    if (!list.length) return '';
    const last = list[0];
    return `<section class="card"><h3>${esc(t('my_lr_title'))}</h3><p class="meta">${esc(t('my_lr_hint'))}</p>
      <div class="lr-card"><div class="lr-card-head"><b>${esc(last.module.name)}
        ${esc(LessonView.unitText(last.unit))}</b><span class="meta">${esc(fmtDate(last.session.date))}</span></div>
        ${LessonView.compactHtml(last, rules, {note: false})}
        ${last.result.level ? `<p>${esc(t('lr_level_' + last.result.level))}</p>` : ''}</div>
      <h4 class="form-section">${esc(t('my_lr_history'))}</h4>${LessonView.historyHtml(list, rules, {note: false})}</section>`;
  }

  function render() {
    const list = data.assessments;
    if (!list.length) {
      host.innerHTML = `${lessonsHtml()}${lessons.ratings.length ? '' : `<div class="card">${App.emptyHtml(t('as_none_own'))}</div>`}`;
      return;
    }
    const prevByTemplate = {};
    const cards = list.map(a => {
      const prev = prevByTemplate[a.template.id];
      prevByTemplate[a.template.id] = a.overall_percent;
      return cardHtml(a, prev);
    }).reverse();
    host.innerHTML = `${lessonsHtml()}<p class="hint">${esc(t('as_own_hint'))}</p>${cards.join('')}`;
  }

  App.onRerender(() => data && render());
  load();
})();

/* Kandidat: Feedback aus abgeschlossenen Bewertungen (neueste zuerst) — nur was fuer den Kandidaten bestimmt ist. */
(() => {
  const {$, esc, t, api, fmtDate} = App;
  const {pct, passBadge} = AssessmentForm;
  const host = $('#page');
  const FIELDS = ['recommendations', 'improvements', 'strengths', 'general_feedback'];
  let items = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      items = (await api('GET', '/api/my-assessments')).assessments.filter(a => FIELDS.some(f => a[f])).reverse();
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function render() {
    if (!items.length) { host.innerHTML = `<div class="card">${App.emptyHtml(t('fb_none'))}</div>`; return; }
    host.innerHTML = `<p class="hint">${esc(t('fb_hint'))}</p>` + items.map((a, i) => `<section class="card${i === 0 ? ' latest' : ''}">
      <div class="pghead"><h3>${esc(a.template.name)}</h3>${passBadge(a.passed)}${i === 0 ? ` <span class="badge ok">${esc(t('fb_latest'))}</span>` : ''}</div>
      <p class="meta">${esc(fmtDate(a.assessed_on))} · ${esc(a.instructor.name)} · ${esc(pct(a.overall_percent))}</p>
      <div class="feedback-grid">${FIELDS.filter(f => a[f]).map(f => `<div><h4>${esc(t('as_f_' + f))}</h4>
        <p class="wrap-text">${esc(a[f])}</p></div>`).join('')}</div></section>`).join('');
  }

  App.onRerender(() => items && render());
  load();
})();

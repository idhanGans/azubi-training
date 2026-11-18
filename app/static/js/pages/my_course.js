/* Kandidat: eigene Kurse — Dozent, Niveau, aktuelles Modul, naechste Termine (keine Teilnehmerliste). */
(() => {
  const {$, esc, t, api} = App;
  const host = $('#page');
  let courses = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      courses = (await api('GET', '/api/my-courses')).courses;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function courseHtml(c) {
    return `<section class="card"><div class="pghead"><h2>${esc(c.name)}</h2>
        <span class="badge">${esc(c.level.code)}</span> <span class="badge ${c.status === 'RUNNING' ? 'ok' : ''}">${esc(t('cs_' + c.status))}</span></div>
      ${c.description ? `<p class="mut wrap-text">${esc(c.description)}</p>` : ''}
      ${Portal.facts([['f_instructor', c.instructor && c.instructor.name], ['f_current_module', c.module && c.module.name]])}
      ${c.module ? `<a class="btn ghost sm" href="/my-modules#module-${c.module.id}">${esc(t('ov_to_modules'))}</a>` : ''}
      <h3 class="section-gap">${esc(t('ov_next_sessions'))}</h3>
      ${c.next_sessions.length ? `<ul class="plain">${c.next_sessions.map(s => Portal.sessionHtml(s, {showDate: true})).join('')}</ul>`
        : App.emptyHtml(t('ms_empty'))}</section>`;
  }

  function render() {
    host.innerHTML = courses.length ? courses.map(courseHtml).join('') : `<div class="card">${App.emptyHtml(t('mc_none'))}</div>`;
  }

  App.onRerender(() => courses && render());
  load();
})();

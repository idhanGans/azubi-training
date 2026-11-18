/* Kandidat: eigene Stammdaten (nur lesen — Aenderungen laufen ueber das Team). */
(() => {
  const {$, esc, t, api, fmtDate} = App;
  const host = $('#page');
  let c = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      c = (await api('GET', '/api/my-profile')).candidate;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  const day = v => (v ? fmtDate(v) : null);

  function render() {
    host.innerHTML = `<div class="card"><div class="profile-head"><div>
        <h2>${esc(c.name)}${c.nickname ? ` <span class="mut">(${esc(c.nickname)})</span>` : ''}</h2>
        <span class="badge">${esc(c.candidate_no)}</span> ${c.status ? `<span class="badge ok">${esc(c.status.name)}</span>` : ''}
      </div></div><p class="hint">${esc(t('mp_hint'))}</p></div>
      <div class="profile-grid">
        <section class="card"><h3>${esc(t('cp_personal'))}</h3>${Portal.facts([
          ['f_email', c.email], ['f_phone', c.phone], ['f_birth', day(c.date_of_birth)], ['f_login', c.msh_user]])}</section>
        <section class="card"><h3>${esc(t('cp_training_info'))}</h3>${Portal.facts([
          ['f_program', c.program && c.program.name], ['f_fach', c.fach], ['f_target_occupation', c.target_occupation],
          ['f_abteilung', c.abteilung], ['f_start', day(c.start_date)], ['f_end', day(c.expected_completion_date)]])}</section>
        <section class="card"><h3>${esc(t('cp_language'))}</h3>${Portal.facts([
          ['mp_current_level', c.current_level && c.current_level.name], ['mp_target_level', c.target_level && c.target_level.name]])}</section>
      </div>`;
  }

  App.onRerender(() => c && render());
  load();
})();

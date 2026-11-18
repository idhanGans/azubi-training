/* Kandidat: eigener Fortschritt — Fertigkeiten, Verlauf, Module, Anwesenheit je Woche. */
(() => {
  const {$, esc, t, api} = App;
  const host = $('#page');
  let data = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', '/api/my-progress');
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function render() {
    host.innerHTML = `<p class="hint">${esc(t('pr_own_hint'))}</p><div id="progress-host"></div>`;
    ProgressView.render($('#progress-host'), data);
  }

  App.onRerender(() => data && render());
  load();
})();

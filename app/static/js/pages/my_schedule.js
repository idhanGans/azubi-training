/* Kandidat: eigener Stundenplan — kommende 4 Wochen, nach Tagen gruppiert (mobil zuerst). */
(() => {
  const {$, esc, t, api, days, todayIso} = App;
  const host = $('#page');
  let sessions = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      sessions = (await api('GET', '/api/my-schedule')).sessions;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function render() {
    if (!sessions.length) {
      host.innerHTML = `<div class="card">${App.emptyHtml(t('ms_empty'))}</div>`;
      return;
    }
    const groups = {};
    sessions.forEach(s => { (groups[s.date] = groups[s.date] || []).push(s); });
    const today = todayIso(), tomorrow = days.add(today, 1);
    host.innerHTML = `<p class="meta">${esc(t('ms_hint', {tz: document.documentElement.dataset.tzLabel}))}</p>` + Object.keys(groups).map(d => `<section class="card">
      <h3>${d === today ? esc(t('cal_today')) + ' · ' : d === tomorrow ? esc(t('ms_tomorrow')) + ' · ' : ''}${esc(days.label(d, {weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric'}))}</h3>
      <ul class="plain">${groups[d].map(x => Portal.sessionHtml(x)).join('')}</ul></section>`).join('');
  }

  App.onRerender(() => sessions && render());
  load();
})();

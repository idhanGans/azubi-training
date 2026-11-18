/* Benachrichtigungen: eigene Liste (ungelesen hervorgehoben), Filter „nur ungelesene", alle als gelesen.
   Der Text entsteht hier aus `nt_<TYPE>` + params — so erscheint er in der gewaehlten Sprache. */
(() => {
  const {$, esc, t, api, fmtDate, fmtDateTime, fmtSlot} = App;
  const host = $('#page');
  let data = null;
  let unreadOnly = false;
  const ICON = {SESSION_REMINDER: 'clock', SESSION_CANCELLED: 'calendar-x', SESSION_MOVED: 'repeat', COURSE_JOINED: 'building',
                ASSESSMENT_PUBLISHED: 'award', ASSESSMENT_CORRECTED: 'pen', ASSESSMENT_DRAFT_OPEN: 'clipboard',
                ATTENDANCE_MISSING: 'check-circle'};

  async function load() {
    try {
      data = await api('GET', `/api/notifications${unreadOnly ? '?unread=1' : ''}`);
      render();
      App.refreshBell();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  /* Platzhalter fuer den Text: Datum/Uhrzeit in Ortsformat. */
  function text(n) {
    const p = n.params, when = (d, s, e) => (d ? (s ? fmtSlot(d, s, e || s) : fmtDate(d)) : '');
    return t('nt_' + n.type, {...p, when: when(p.date, p.start, p.end), old_when: when(p.old_date, p.old_start, p.old_end),
      date: p.date ? fmtDate(p.date) : '', start: p.start || '', reason: p.reason || '–'});
  }

  function render() {
    const list = data.notifications;
    host.innerHTML = `<div class="pghead"><p class="hint inline">${esc(t('nt_hint'))}</p><div class="tools">
        <label class="meta"><input type="checkbox" data-unread${unreadOnly ? ' checked' : ''}> ${esc(t('nt_only_unread'))}</label>
        ${data.unread ? `<button class="btn ghost sm" type="button" data-all>${esc(t('nt_read_all'))}</button>` : ''}</div></div>
      <div class="card">${list.length ? `<ul class="plain notif-list">${list.map(n => `<li class="notif${n.read ? '' : ' unread'}">
          <span class="notif-icon">${App.icon(ICON[n.type] || 'bell')}</span>
          <div><a href="${esc(n.link || '#')}" data-id="${n.id}">${esc(text(n))}</a>
            <div class="meta">${esc(fmtDateTime(n.created_at))}${n.read ? '' : ` · <b>${esc(t('nt_unread'))}</b>`}</div></div>
          ${n.read ? '' : `<button class="btn ghost sm" type="button" data-read="${n.id}" aria-label="${esc(t('nt_mark_read'))}">${App.icon('check')}</button>`}
        </li>`).join('')}</ul>` : App.emptyHtml(t(unreadOnly ? 'nt_none_unread' : 'nt_none'))}</div>`;
  }

  host.addEventListener('change', ev => { if (ev.target.hasAttribute('data-unread')) { unreadOnly = ev.target.checked; load(); } });
  host.addEventListener('click', async ev => {
    const read = ev.target.closest('[data-read]');
    const all = ev.target.closest('[data-all]');
    const link = ev.target.closest('a[data-id]');
    try {
      if (read) { await api('POST', `/api/notifications/${read.dataset.read}/read`, {}); await load(); }
      if (all) { await api('POST', '/api/notifications/read-all', {}); await load(); }
      if (link) {   // beim Oeffnen als gelesen markieren, dann weiter zum Link
        ev.preventDefault();
        await api('POST', `/api/notifications/${link.dataset.id}/read`, {});
        location.href = link.getAttribute('href');
      }
    } catch (err) { App.toast(err.message, 'error'); }
  });
  App.onRerender(() => data && render());
  host.innerHTML = App.loadingHtml();
  load();
})();

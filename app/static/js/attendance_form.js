/* Attendance: capture dialog per session + display helpers (rate "94 %"). */
const AttendanceForm = (() => {
  const {esc, t, can, api, fmtNum, toast} = App;
  const STATUSES = ['PRESENT', 'LATE', 'EXCUSED', 'ABSENT'];

  const rateText = rate => (rate == null ? '–' : `${fmtNum(rate * 100, 0)} %`);
  const statusBadge = status => `<span class="badge ${status === 'PRESENT' ? 'ok' : status === 'ABSENT' ? 'warn' : ''}">${esc(t('at_' + status))}</span>`;
  const countsText = s => t('at_counts', {p: s.present, l: s.late, e: s.excused, a: s.absent});

  function rowHtml(e, editable) {
    const a = e.attendance || {};
    const tr = e.trainee;
    const name = `${esc(tr.name)}${tr.nickname ? ` <span class="mut">(${esc(tr.nickname)})</span>` : ''}`;
    const left = !tr.in_course ? ` <span class="meta">${esc(t('at_left_course'))}</span>` : '';
    if (!editable || tr.archived) {            // whoever switched the group stays correctable
      return `<tr class="archived"><td>${name}${left}</td>
        <td>${a.status ? statusBadge(a.status) + (a.minutes_late ? ` <span class="meta">${esc(t('at_minutes', {n: a.minutes_late}))}</span>` : '') : '–'}</td>
        <td>${esc(a.note || '')}</td></tr>`;
    }
    const group = `at_${tr.id}`;
    return `<tr data-trainee="${tr.id}"${tr.in_course ? '' : ' data-former'}><td>${name}${left}</td>
      <td><div class="att-choice" role="radiogroup" aria-label="${esc(tr.name)}">${STATUSES.map(s => `<label class="att-${s.toLowerCase()}">
        <input type="radio" name="${group}" value="${s}"${a.status === s ? ' checked' : ''}><span>${esc(t('at_' + s))}</span></label>`).join('')}</div>
        <input class="input att-min" type="number" min="1" max="600" name="min_${tr.id}" value="${esc(a.minutes_late || '')}"
          placeholder="${esc(t('at_min_ph'))}" aria-label="${esc(t('at_min_label', {name: tr.name}))}"${a.status === 'LATE' ? '' : ' hidden'}></td>
      <td><input class="input" name="note_${tr.id}" maxlength="500" value="${esc(a.note || '')}" placeholder="${esc(t('at_note'))}" aria-label="${esc(t('at_note_label', {name: tr.name}))}"></td></tr>`;
  }

  async function open(session, onSaved) {
    let data;
    try { data = await api('GET', `/api/sessions/${session.id}/attendance`); } catch (err) { toast(err.message, 'error'); return; }
    const editable = can('attendance.manage') && data.session.status !== 'CANCELLED';
    const s = data.session;
    const dlg = App.openDialog(t('at_title'), `<form novalidate>
      <p class="meta">${esc(s.course.name)} · ${esc(App.fmtSlot(s.date, s.start, s.end))}</p>
      ${data.entries.length ? `<div class="tbl-wrap"><table class="tbl att-table"><thead><tr><th>${esc(t('f_name'))}</th>
        <th>${esc(t('f_status'))}</th><th>${esc(t('at_note'))}</th></tr></thead>
        <tbody>${data.entries.map(e => rowHtml(e, editable)).join('')}</tbody></table></div>` : App.emptyHtml(t('co_no_participants'))}
      <p class="meta">${esc(t('at_note_hint'))}</p>
      ${editable && data.entries.length ? `<div class="form-actions">
        <button class="btn" type="submit">${esc(t('save'))}</button>
        <button class="btn ghost" type="button" data-all>${esc(t('at_all_present'))}</button>
        <span class="form-error" role="alert"></span></div>` : ''}</form>`);
    const form = dlg.querySelector('form');
    form.addEventListener('change', ev => {
      if (ev.target.type !== 'radio') return;
      const row = ev.target.closest('tr');
      row.querySelector('.att-min').hidden = ev.target.value !== 'LATE';
    });
    const all = form.querySelector('[data-all]');
    if (all) all.addEventListener('click', () => {
      form.querySelectorAll('tr[data-trainee]:not([data-former])').forEach(row => {
        if (!row.querySelector('input[type=radio]:checked')) row.querySelector('input[value=PRESENT]').checked = true;
        row.querySelector('.att-min').hidden = row.querySelector('input[type=radio]:checked').value !== 'LATE';
      });
    });
    form.addEventListener('submit', async ev => {
      ev.preventDefault();
      const errorSlot = form.querySelector('.form-error');
      errorSlot.textContent = '';
      const entries = [...form.querySelectorAll('tr[data-trainee]')].map(row => {
        const checked = row.querySelector('input[type=radio]:checked');
        if (!checked) return null;
        const id = +row.dataset.trainee;
        const entry = {trainee_id: id, status: checked.value, note: row.querySelector(`[name=note_${id}]`).value};
        if (checked.value === 'LATE' && row.querySelector('.att-min').value) entry.minutes_late = +row.querySelector('.att-min').value;
        return entry;
      }).filter(Boolean);
      if (!entries.length) { errorSlot.textContent = t('at_none_selected'); return; }
      const btn = form.querySelector('[type=submit]');
      btn.disabled = true;
      try {
        await api('PUT', `/api/sessions/${session.id}/attendance`, {entries});
        const missing = form.querySelectorAll('tr[data-trainee]:not([data-former])').length
          - entries.filter(e => !form.querySelector(`tr[data-trainee="${e.trainee_id}"][data-former]`)).length;
        toast(missing ? t('at_saved_missing', {n: missing}) : t('at_saved'), missing ? 'warn' : 'ok');
        dlg.close();
        if (onSaved) await onSaved();
      } catch (err) {
        errorSlot.textContent = err.message;
      } finally {
        btn.disabled = false;
      }
    });
  }

  return {open, rateText, statusBadge, countsText};
})();

/* Tages-Report des Kandidaten: Formular + Absenden — auf „Mein Trainings-Report" und in der Karte „Heute"
   der Übersicht (dort gleich nach dem Anmelden ausfüllbar, wie im alten Trainings-Monitoring). */
const ReportForm = (() => {
  const {esc, t, api, todayIso} = App;

  /* r = vorhandener Report (Bearbeiten) oder null (neu); mit `cancel` erscheint „Abbrechen". */
  function html(r, {cancel} = {}) {
    return `<form id="report-form" novalidate>
      <div class="form-row"><label for="f_period">${esc(t('f_date'))}</label><div class="field">
        <input id="f_period" name="period" type="date" class="input" required value="${esc(r ? r.period || todayIso() : todayIso())}">
        <div class="field-error" data-error-for="period"></div></div></div>
      <div class="form-row"><label for="f_hours">${esc(t('f_hours'))}</label><div class="field">
        <input id="f_hours" name="hours" type="number" min="0" max="24" step="0.5" class="input" placeholder="${esc(t('ph_hours'))}" value="${esc(r && r.hours != null ? r.hours : '')}">
        <div class="field-error" data-error-for="hours"></div></div></div>
      <div class="form-row"><span class="flabel">${esc(t('f_area'))}</span><div class="field checks">
        <label><input type="checkbox" name="lang"${r && r.lang ? ' checked' : ''}> ${esc(t('f_lang'))}</label>
        <label><input type="checkbox" name="tech"${r && r.tech ? ' checked' : ''}> ${esc(t('f_tech'))}</label></div></div>
      <div class="form-row"><label for="f_station">${esc(t('f_station'))}</label><div class="field">
        <input id="f_station" name="station" class="input" maxlength="120" placeholder="${esc(t('ph_station'))}" value="${esc(r ? r.station : '')}">
        <div class="field-error" data-error-for="station"></div></div></div>
      <div class="form-row"><label for="f_learned">${esc(t('f_learned'))}</label><div class="field">
        <textarea id="f_learned" name="learned" class="input" rows="4" maxlength="2000" placeholder="${esc(t('ph_learned'))}">${esc(r ? r.learned : '')}</textarea>
        <div class="field-error" data-error-for="learned"></div></div></div>
      <div class="form-actions"><button class="btn" type="submit">${esc(t(r ? 'c_update' : 'c_submit'))}</button>
        ${cancel ? `<button class="btn ghost" type="button" data-action="cancel">${esc(t('cancel'))}</button>` : ''}
        <span class="form-error" role="alert"></span></div>
    </form>`;
  }

  /* Absenden (neu bzw. `editId` aendern). true bei Erfolg, sonst stehen die Fehler im Formular. */
  async function submit(form, editId) {
    form.querySelectorAll('.field-error').forEach(e => { e.textContent = ''; });
    form.querySelector('.form-error').textContent = '';
    if (!App.validate(form)) return false;
    const body = {period: form.period.value, hours: form.hours.value, lang: form.lang.checked,
                  tech: form.tech.checked, station: form.station.value, learned: form.learned.value};
    if (!body.hours && !body.learned.trim()) {
      App.showFormError(form, new App.ApiError(400, t('c_need_one'), 'hours'));
      return false;
    }
    const btn = form.querySelector('[type=submit]');
    btn.disabled = true;
    try {
      await api(editId ? 'PUT' : 'POST', editId ? `/api/training/me/${editId}` : '/api/training/me', body);
      return true;
    } catch (err) {
      btn.disabled = false;
      App.showFormError(form, err);
      return false;
    }
  }

  return {html, submit};
})();

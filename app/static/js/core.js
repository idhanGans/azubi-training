/* Common helpers for all pages: language, API, formatting, states, dialogs. */
const App = (() => {
  const LOCALES = {de: 'de-DE', en: 'en-GB', id: 'id-ID'};
  /* Time zone of the school (local_time.TZ_NAME): timestamps and "today" apply there, not on the device —
     a phone in Jakarta shows the same times as the schedule. */
  const TZ = document.documentElement.dataset.tz;
  let lang = localStorage.getItem('azubitr_lang');
  if (!LOCALES[lang]) lang = 'de';
  const rerenderHooks = [];

  const $ = (sel, root) => (root || document).querySelector(sel);
  /* Icon from static/icons.svg (decorative, text is next to it) — no emojis in the UI. */
  const ICONS = document.documentElement.dataset.icons;
  const icon = (name, cls) => `<svg class="ic${cls ? ' ' + cls : ''}" aria-hidden="true" focusable="false"><use href="${ICONS}#i-${name}"></use></svg>`;
  const esc = s => (s == null ? '' : String(s)).replace(/[&<>"']/g,
    c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  function t(key, vars) {
    const entry = I18N[key];
    let s = entry ? (entry[lang] || entry.de) : key;
    for (const k in (vars || {})) s = s.split('{' + k + '}').join(vars[k]);
    return s;
  }

  function applyI18n(root) {
    (root || document).querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    (root || document).querySelectorAll('[data-i18n-aria]').forEach(el => el.setAttribute('aria-label', t(el.dataset.i18nAria)));
    document.documentElement.lang = lang;
    document.querySelectorAll('.langsel button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lang === lang)));
    const h1 = $('.topbar h1');
    if (h1) document.title = h1.textContent + ' · Azubi-Training';
  }

  function setLang(next) {
    lang = next;
    localStorage.setItem('azubitr_lang', next);
    applyI18n();
    rerenderHooks.forEach(fn => fn());
  }

  /* ---------- Formatting (German: 25.09.2026, 10:00 Uhr, 78,4) ---------- */
  function fmtDate(isoDay) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDay || '');
    if (!m) return isoDay || '–';
    return new Date(Date.UTC(+m[1], m[2] - 1, +m[3])).toLocaleDateString(LOCALES[lang],
      {day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC'});
  }
  function fmtDateTime(iso) {
    if (!iso) return '–';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const s = d.toLocaleString(LOCALES[lang], {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit',
                                               minute: '2-digit', timeZone: TZ});
    return lang === 'de' ? s + ' Uhr' : s;
  }
  function fmtNum(n, digits) {
    if (n == null || n === '') return '–';
    return Number(n).toLocaleString(LOCALES[lang], {maximumFractionDigits: digits == null ? 1 : digits});
  }
  /* Time range from local-time fields of the API: "10:00–12:00 Uhr" (no conversion in the browser). */
  const fmtTimeRange = (start, end) => `${start}–${end}` + (lang === 'de' ? ' Uhr' : '');
  /* Session: "25.09.2026, 10:00–12:00 Uhr" */
  const fmtSlot = (day, start, end) => `${fmtDate(day)}, ${fmtTimeRange(start, end)}`;
  /* "Angelegt am … von …" (created on … by …) (key `key` + `key_at`) — without a known login only the date, never "von –". */
  const stamp = (key, at, by) => (by ? t(key, {d: fmtDateTime(at), u: by}) : t(key + '_at', {d: fmtDateTime(at)}));

  /* Calendar arithmetic on 'YYYY-MM-DD' (UTC midnight, so no time zone interferes). */
  const isoToDate = iso => { const [y, m, d] = iso.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)); };
  const dateToIso = d => d.toISOString().slice(0, 10);
  const days = {
    add: (iso, n) => { const d = isoToDate(iso); d.setUTCDate(d.getUTCDate() + n); return dateToIso(d); },
    weekday: iso => (isoToDate(iso).getUTCDay() + 6) % 7,          // 0 = Monday
    monday: iso => days.add(iso, -days.weekday(iso)),
    monthStart: iso => iso.slice(0, 8) + '01',
    addMonths: (iso, n) => { const d = isoToDate(iso.slice(0, 8) + '01'); d.setUTCMonth(d.getUTCMonth() + n); return dateToIso(d); },
    label: (iso, opts) => isoToDate(iso).toLocaleDateString(LOCALES[lang], {...opts, timeZone: 'UTC'}),
  };

  /* 'YYYY-MM-DD' of today in the school's time zone (en-CA formats exactly like this). */
  const todayIso = () => new Date().toLocaleDateString('en-CA', {timeZone: TZ});

  /* ---------- API ---------- */
  class ApiError extends Error {
    constructor(status, message, field) { super(message); this.status = status; this.field = field; }
  }
  async function api(method, url, body) {
    const upload = body instanceof FormData;
    const headers = upload ? {'Accept': 'application/json', 'X-Requested-With': 'fetch'}
                           : {'Content-Type': 'application/json', 'Accept': 'application/json'};
    let res;
    try {
      res = await fetch(url, {method, headers,
                              body: body === undefined ? undefined : upload ? body : JSON.stringify(body)});
    } catch (e) {
      throw new ApiError(0, t('err_network'));          // offline / server not reachable
    }
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (res.ok) return data;
    if (res.status === 401) throw new ApiError(401, t('err_session'));
    if (res.status === 403 && data && data.code === 'FORBIDDEN') throw new ApiError(403, t('err_forbidden'));
    if (res.status === 413) throw new ApiError(413, (data && data.error) || t('err_too_large'), 'file');
    if (data && data.error && res.status < 500) throw new ApiError(res.status, data.error, data.field);
    throw new ApiError(res.status, method === 'GET' ? t('err_load') : t('err_save'));
  }

  /* ---------- States ---------- */
  const loadingHtml = () => `<div class="state" role="status">${esc(t('loading'))}</div>`;
  const emptyHtml = text => `<div class="state">${esc(text)}</div>`;
  function showError(host, err, retry) {
    host.innerHTML = `<div class="card"><div class="state error" role="alert">${esc(err.message || t('err_load'))}
      ${retry ? `<div><button class="btn ghost" type="button">${esc(t('retry'))}</button></div>` : ''}</div></div>`;
    if (retry) host.querySelector('button').addEventListener('click', retry);
  }
  function toast(message, kind) {
    const el = document.createElement('div');
    el.className = 'toast ' + (kind || 'ok');
    el.textContent = message;
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }
  /* After saving, navigating to another page: the confirmation appears there (otherwise it would be lost). */
  const FLASH = 'azubitr_flash';
  function goWithToast(url, message) {
    sessionStorage.setItem(FLASH, message);
    location.href = url;
  }
  const flash = sessionStorage.getItem(FLASH);
  if (flash) { sessionStorage.removeItem(FLASH); toast(flash); }

  /* ---------- Dialogs ---------- */
  function openDialog(title, bodyHtml, narrow) {
    const dlg = document.createElement('dialog');
    if (narrow) dlg.className = 'narrow';
    dlg.innerHTML = `<div class="dlg-head"><h3>${esc(title)}</h3>
      <button type="button" class="dlg-close" aria-label="${esc(t('close'))}">${icon('x')}</button></div>
      <div class="dlg-body">${bodyHtml}</div>`;
    document.body.appendChild(dlg);
    dlg.querySelector('.dlg-close').addEventListener('click', () => dlg.close());
    dlg.addEventListener('close', () => dlg.remove());
    dlg.showModal();
    return dlg;
  }

  function fieldHtml(f) {
    if (f.heading) return `<h4 class="form-section">${esc(f.heading)}</h4>`;
    const id = 'f_' + f.name;
    const attrs = `id="${id}" name="${esc(f.name)}" class="input"${f.required ? ' required' : ''}`
      + (f.min != null ? ` min="${f.min}"` : '') + (f.max != null ? ` max="${f.max}"` : '')
      + (f.step != null ? ` step="${f.step}"` : '') + (f.maxlength ? ` maxlength="${f.maxlength}"` : '')
      + (f.placeholder ? ` placeholder="${esc(f.placeholder)}"` : '');
    const extra = `${f.hint ? `<div class="meta">${esc(f.hint)}</div>` : ''}<div class="field-error" data-error-for="${esc(f.name)}"></div>`;
    if (f.type === 'checks' || f.type === 'custom') {  // group without a single input field -> group label
      const body = f.type === 'custom' ? f.html : `<div class="checks">${f.options.map(o => `<label>
        <input type="checkbox" name="${esc(f.name)}" value="${esc(o.value)}"${(f.value || []).includes(o.value) ? ' checked' : ''}> ${esc(o.label)}</label>`).join('')}</div>`;
      return `<div class="form-row" role="group" aria-labelledby="${id}_l"><span class="flabel" id="${id}_l">${esc(f.label)}</span>
        <div class="field">${body}${extra}</div></div>`;
    }
    let control;
    if (f.type === 'select') {
      control = `<select ${attrs}>${f.options.map(o => `<option value="${esc(o.value)}"${o.value === (f.value || '') ? ' selected' : ''}>${esc(o.label)}</option>`).join('')}</select>`;
    } else if (f.type === 'textarea') {
      control = `<textarea ${attrs} rows="${f.rows || 3}">${esc(f.value)}</textarea>`;
    } else if (f.type === 'file') {
      control = `<input type="file" ${attrs}${f.accept ? ` accept="${esc(f.accept)}"` : ''}>`;
    } else {
      control = `<input type="${f.type || 'text'}" ${attrs} value="${esc(f.value)}">`;
    }
    return `<div class="form-row"><label for="${id}">${esc(f.label)}</label><div class="field">${control}${extra}</div></div>`;
  }

  /* Check required fields/limits like reportValidity(), but with our own texts in the
     chosen language — otherwise the browser messages come in the browser's language. */
  function validityText(el) {
    const v = el.validity;
    if (v.valueMissing) return t(el.type === 'file' ? 'val_file' : el.tagName === 'SELECT' ? 'val_select' : 'val_required');
    if (v.typeMismatch) return t(el.type === 'email' ? 'val_email' : 'val_url');
    if (v.badInput) return t('val_bad_input');
    if (v.rangeUnderflow) return t('val_min', {n: fmtNum(+el.min, 2)});
    if (v.rangeOverflow) return t('val_max', {n: fmtNum(+el.max, 2)});
    if (v.stepMismatch) return t('val_step', {n: fmtNum(+el.step, 2)});
    if (v.tooLong) return t('val_too_long', {n: el.maxLength});
    return t('val_invalid');
  }

  function validate(form) {
    for (const el of form.elements) {
      if (!el.willValidate) continue;
      el.setCustomValidity('');
      if (el.validity.valid) continue;
      el.setCustomValidity(validityText(el));
      el.addEventListener('input', () => el.setCustomValidity(''), {once: true});
    }
    return form.reportValidity();
  }

  /* Form dialog. onSubmit(values, formData) saves; if it throws an ApiError,
     the dialog stays open and shows the error on the field or at the bottom.
     Field types: text/email/number/date/time, select, textarea, file,
     checks (multi-select -> formData.getAll(name)), custom (own HTML). */
  function formDialog({title, intro, fields, submitLabel, onSubmit}) {
    const dlg = openDialog(title, `<form novalidate>${intro ? `<p class="hint">${esc(intro)}</p>` : ''}
      ${fields.map(fieldHtml).join('')}
      <div class="form-actions"><button class="btn" type="submit">${esc(submitLabel || t('save'))}</button>
      <button class="btn ghost" type="button" data-cancel>${esc(t('cancel'))}</button>
      <span class="form-error" role="alert"></span></div></form>`, true);
    const form = dlg.querySelector('form');
    form.querySelector('[data-cancel]').addEventListener('click', () => dlg.close());
    form.addEventListener('submit', async ev => {
      ev.preventDefault();
      form.querySelectorAll('.field-error').forEach(e => { e.textContent = ''; });
      form.querySelectorAll('[aria-invalid]').forEach(e => e.removeAttribute('aria-invalid'));
      form.querySelector('.form-error').textContent = '';
      if (!validate(form)) return;
      const formData = new FormData(form);
      const values = Object.fromEntries(formData.entries());
      const btn = form.querySelector('[type=submit]');
      btn.disabled = true;
      try {
        await onSubmit(values, formData);
        dlg.close();
      } catch (err) {
        showFormError(form, err);
      } finally {
        btn.disabled = false;
      }
    });
    return dlg;
  }

  function showFormError(form, err) {
    const slot = err.field && form.querySelector(`[data-error-for="${err.field}"]`);
    if (slot) {
      slot.textContent = err.message;
      const input = form.querySelector(`[name="${err.field}"]`);
      if (input) { input.setAttribute('aria-invalid', 'true'); input.focus(); }
    } else {
      form.querySelector('.form-error').textContent = err.message || t('err_save');
    }
  }

  function confirmDialog(text) {
    return new Promise(resolve => {
      let answer = false;
      const dlg = openDialog(t('confirm'), `<p>${esc(text)}</p><div class="form-actions">
        <button class="btn" type="button" data-yes>${esc(t('confirm'))}</button>
        <button class="btn ghost" type="button" data-no>${esc(t('cancel'))}</button></div>`, true);
      dlg.querySelector('[data-yes]').addEventListener('click', () => { answer = true; dlg.close(); });
      dlg.querySelector('[data-no]').addEventListener('click', () => dlg.close());
      dlg.addEventListener('close', () => resolve(answer));
    });
  }

  /* Click delegation: <button data-action="name" data-id="1"> -> handlers.name(id, el) */
  function onActions(root, handlers) {
    root.addEventListener('click', ev => {
      const el = ev.target.closest('[data-action]');
      if (el && handlers[el.dataset.action]) handlers[el.dataset.action](el.dataset.id ? +el.dataset.id : null, el);
    });
  }

  document.querySelectorAll('.langsel button').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));
  const menuBtn = $('#menubtn');
  if (menuBtn) menuBtn.addEventListener('click', () => {
    const open = document.body.classList.toggle('nav-open');
    menuBtn.setAttribute('aria-expanded', String(open));
  });
  applyI18n();

  /* Bell: number of unread notifications (generates due reminders in the process). */
  async function refreshBell() {
    const bell = $('.bell');
    if (!bell) return;
    try {
      const {unread} = await api('GET', '/api/notifications/count');
      const badge = bell.querySelector('.bell-count');
      badge.textContent = unread > 99 ? '99+' : String(unread);
      badge.hidden = !unread;
      bell.setAttribute('aria-label', unread ? t('nt_bell_unread', {n: unread}) : t('nt_title'));
    } catch (err) { /* the bell is extra — the page keeps running without it */ }
  }
  refreshBell();

  /* Set title + breadcrumb from loaded data (e.g. module name).
     trail: [{href, label}] without "Start" and without the page itself. */
  function setPageTitle(title, trail) {
    const h1 = $('.topbar h1');
    h1.textContent = title;
    h1.removeAttribute('data-i18n');
    document.title = title + ' · Azubi-Training';
    const links = [{href: '/', label: t('crumb_home')}, ...(trail || [])];
    $('.crumbs').innerHTML = links.map(c => `<a href="${esc(c.href)}">${esc(c.label)}</a>`).join(' / ') + ' / ' + esc(title);
  }

  /* Only for display (showing/hiding buttons) — checked in the backend. */
  const permissions = new Set((document.body.dataset.permissions || '').split(' ').filter(Boolean));
  const can = p => permissions.has(p);

  return {$, esc, icon, stamp, t, can, setPageTitle, refreshBell, applyI18n, onRerender: fn => rerenderHooks.push(fn),
          fmtDate, fmtDateTime, fmtNum, fmtTimeRange, fmtSlot, days, todayIso, api, ApiError,
          loadingHtml, emptyHtml, showError, toast, goWithToast, openDialog, formDialog, validate, showFormError, confirmDialog, onActions};
})();

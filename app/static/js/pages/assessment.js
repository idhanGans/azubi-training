/* Capture/view assessment: points per category or subcategory, result
   (preview from the server, never computed in the browser), feedback for the candidate and,
   separately, the internal note. Save draft, finalize, correct. */
(() => {
  const {$, esc, t, api, fmtDate, fmtDateTime, fmtNum, toast} = App;
  const {pct, passBadge, statusBadge} = AssessmentForm;
  const host = $('#page');
  const id = +host.dataset.assessmentId;
  const FEEDBACK = ['strengths', 'improvements', 'recommendations', 'general_feedback'];
  let data = null;
  let result = null;
  let correcting = false;
  let timer = null;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      data = await api('GET', `/api/assessments/${id}`);
      result = data.result;
      correcting = false;
      render();
    } catch (err) {
      App.showError(host, err, err.status === 404 ? null : load);
    }
  }

  const a = () => data.assessment;
  const editable = () => data.can_edit && (a().status === 'DRAFT' || correcting);
  const pointsOf = key => {
    const s = a().scores.find(x => (key[0] === 'criterion' ? x.criterion_id : x.category_id) === key[1]);
    return s ? s.points : null;
  };

  function input(key, max, label) {
    const value = pointsOf(key);
    if (!editable()) return `<span class="pts">${esc(value == null ? '–' : fmtNum(value, 1))}</span>`;
    return `<input class="input pts" type="number" min="0" max="${max}" step="0.5" inputmode="decimal"
      data-kind="${key[0]}" data-key="${key[1]}" value="${value == null ? '' : value}" aria-label="${esc(label)}">`;
  }

  function categoryRows(cat, res) {
    const head = `<tr class="cat-row"><th scope="row">${esc(cat.name)}
        <span class="meta">${esc(t('as_weight_short', {w: fmtNum(cat.weight, 2)}))}${cat.passing_score != null
          ? ' · ' + esc(t('as_min_short', {p: fmtNum(cat.passing_score, 1)})) : ''}</span>
        ${cat.description ? `<div class="meta">${esc(cat.description)}</div>` : ''}</th>
      <td class="nw">${cat.criteria.length ? `<span data-cat-sum="${cat.id}">${esc(res.points_so_far == null ? '–' : fmtNum(res.points_so_far, 1))}</span>`
        : input(['category', cat.id], cat.max_score, cat.name)} <span class="mut">/ ${esc(fmtNum(cat.max_score, 1))}</span></td>
      <td class="nw" data-cat-pct="${cat.id}">${esc(pct(res.percent))}</td>
      <td class="nw" data-cat-pass="${cat.id}">${passBadge(res.passed)}</td></tr>`;
    const subs = cat.criteria.map(cr => `<tr class="sub-row"><th scope="row">${esc(cr.name)}</th>
      <td class="nw">${input(['criterion', cr.id], cr.max_score, `${cat.name} – ${cr.name}`)} <span class="mut">/ ${esc(fmtNum(cr.max_score, 1))}</span></td>
      <td></td><td></td></tr>`).join('');
    return head + subs;
  }

  function resultHtml() {
    const r = result;
    return `<div class="result-box ${r.passed == null ? '' : r.passed ? 'ok' : 'warn'}" aria-live="polite">
      <span class="meta">${esc(t('as_overall'))}</span><b>${esc(pct(r.overall_percent))}</b>
      <span>${r.complete ? passBadge(r.passed) : `<span class="meta">${esc(t('as_incomplete'))}</span>`}</span>
      <p class="meta">${esc(t('as_rule', {p: fmtNum(r.passing_percent, 1)}))}</p></div>`;
  }

  function textsHtml() {
    const x = a();
    const box = (name, rows) => editable()
      ? `<textarea class="input" name="${name}" rows="${rows}" maxlength="4000" aria-label="${esc(t('as_f_' + name))}">${esc(x[name] || '')}</textarea>`
      : `<p class="wrap-text">${esc(x[name] || '–')}</p>`;
    return `<section class="card feedback-box"><h3>${esc(t('as_feedback'))}</h3><p class="meta">${esc(t('as_feedback_hint'))}</p>
        <div class="feedback-grid">${FEEDBACK.map(f => `<div><h4>${esc(t('as_f_' + f))}</h4>${box(f, 3)}</div>`).join('')}</div></section>
      <section class="card internal-box"><h3>${App.icon('lock')} ${esc(t('as_f_internal_note'))}</h3><p class="meta">${esc(t('as_internal_hint'))}</p>
        ${box('internal_note', 3)}</section>`;
  }

  function actionsHtml() {
    const x = a();
    if (!data.can_edit) return '';
    if (x.status === 'DRAFT') {
      return `<div class="form-actions sticky-actions"><button class="btn" type="button" data-action="finalize">${esc(t('as_finalize'))}</button>
        <button class="btn ghost" type="button" data-action="save">${esc(t('as_save_draft'))}</button>
        <button class="btn ghost danger-text" type="button" data-action="discard">${esc(t('as_discard'))}</button>
        <span class="form-error" role="alert"></span></div>`;
    }
    if (!correcting) return `<div class="form-actions"><button class="btn ghost" type="button" data-action="correct">${esc(t('as_correct'))}</button></div>`;
    return `<div class="form-actions sticky-actions"><input class="input" name="reason" maxlength="500" required aria-required="true" placeholder="${esc(t('as_reason_ph'))}" aria-label="${esc(t('as_reason'))}">
      <button class="btn" type="button" data-action="save">${esc(t('as_save_correction'))}</button>
      <button class="btn ghost" type="button" data-action="cancel">${esc(t('cancel'))}</button>
      <span class="form-error" role="alert"></span></div>`;
  }

  function render() {
    const x = a(), tpl = data.template;
    App.setPageTitle(`${x.trainee.name} – ${tpl.name}`, [{href: '/assessments', label: t('nav_assessments')}]);
    const byId = Object.fromEntries(result.categories.map(c => [c.id, c]));
    host.innerHTML = `
      <div class="card"><div class="profile-head"><div>
        <h2><a href="/candidates/${x.trainee.id}">${esc(x.trainee.name)}</a> <span class="mut">${esc(x.trainee.candidate_no)}</span></h2>
        ${statusBadge(x.status)} <span class="badge">${esc(tpl.name)}</span>
        <p class="meta">${esc(t('as_meta', {d: fmtDate(x.assessed_on), e: x.instructor.name}))}${x.course ? ' · ' + esc(x.course.name) : ''}
          ${x.finalized_at ? ' · ' + esc(t('as_finalized_at', {d: fmtDateTime(x.finalized_at)})) : ''}</p>
        ${editable() && x.status === 'DRAFT' ? `<label class="inline-field">${esc(t('f_date'))}
          <input class="input" type="date" name="assessed_on" value="${esc(x.assessed_on)}"></label>` : ''}
      </div>${resultHtml()}</div></div>
      ${correcting ? `<div class="card notice">${esc(t('as_correcting_hint'))}</div>` : ''}
      <section class="card"><h3>${esc(t('as_scores'))}</h3>
        <div class="tbl-wrap"><table class="tbl score-tbl"><thead><tr><th>${esc(t('as_category'))}</th><th>${esc(t('as_points'))}</th>
          <th>${esc(t('as_percent'))}</th><th>${esc(t('f_status'))}</th></tr></thead>
          <tbody>${tpl.categories.map(c => categoryRows(c, byId[c.id])).join('')}</tbody></table></div>
        ${editable() ? `<p class="meta">${esc(t('as_points_hint'))}</p>` : ''}</section>
      ${textsHtml()}
      ${actionsHtml()}
      ${historyHtml()}`;
  }

  /* Who changed what and when (creation, finalization, corrections with old -> new and reason) — from the server. */
  function historyHtml() {
    if (!data.history || !data.history.length) return '';
    return `<section class="card"><h3>${esc(t('as_history'))}</h3>
      ${ActivityList.tableHtml([...data.history].reverse(), {showEntity: false})}</section>`;
  }

  function collectScores() {
    return [...host.querySelectorAll('input.pts')].map(el => {
      const raw = el.value.trim().replace(',', '.');
      return {[el.dataset.kind === 'criterion' ? 'criterion_id' : 'category_id']: +el.dataset.key,
              points: raw === '' ? null : Number(raw)};
    });
  }

  function collect() {
    const body = {scores: collectScores()};
    [...FEEDBACK, 'internal_note'].forEach(f => { body[f] = host.querySelector(`[name="${f}"]`).value; });
    const day = host.querySelector('[name="assessed_on"]');
    if (day) body.assessed_on = day.value;
    const reason = host.querySelector('[name="reason"]');
    if (reason && reason.value.trim()) body.reason = reason.value.trim();
    return body;
  }

  /* Preview: the same calculation as on save, from the server. */
  async function preview() {
    if (!editable()) return;
    const scores = collectScores().filter(s => s.points != null && !Number.isNaN(s.points));
    let next;
    try {
      next = await api('POST', `/api/assessment-templates/${data.template.id}/evaluate`, {scores});
    } catch (err) {
      if (editable()) host.querySelector('.form-error').textContent = err.message;
      return;
    }
    if (!editable()) return;          // meanwhile saved/cancelled — discard the response
    result = next;
    host.querySelector('.form-error').textContent = '';
    result.categories.forEach(c => {
      const sum = host.querySelector(`[data-cat-sum="${c.id}"]`);
      if (sum) sum.textContent = c.points_so_far == null ? '–' : fmtNum(c.points_so_far, 1);
      host.querySelector(`[data-cat-pct="${c.id}"]`).textContent = pct(c.percent);
      host.querySelector(`[data-cat-pass="${c.id}"]`).innerHTML = passBadge(c.passed);
    });
    host.querySelector('.result-box').outerHTML = resultHtml();
  }

  host.addEventListener('input', ev => {
    if (!ev.target.classList.contains('pts')) return;
    clearTimeout(timer);
    timer = setTimeout(preview, 300);
  });

  async function send(method, url, okText) {
    clearTimeout(timer);              // no trailing preview on the newly rendered page
    const errorSlot = host.querySelector('.form-error');
    errorSlot.textContent = '';
    host.querySelectorAll('.form-actions button').forEach(b => { b.disabled = true; });
    try {
      data = await api(method, url, collect());
      result = data.result;
      correcting = false;
      toast(okText);
      render();
    } catch (err) {
      errorSlot.textContent = err.message;
      host.querySelectorAll('.form-actions button').forEach(b => { b.disabled = false; });
      if (err.field === 'reason') host.querySelector('[name="reason"]').focus();
    }
  }

  App.onActions(host, {
    save: () => send('PATCH', `/api/assessments/${id}`, t(a().status === 'FINAL' ? 'as_corrected' : 'as_saved_draft')),
    finalize: async () => {
      if (!await App.confirmDialog(t('as_finalize_confirm'))) return;
      await send('POST', `/api/assessments/${id}/finalize`, t('as_finalized'));
    },
    discard: async () => {
      if (!await App.confirmDialog(t('as_discard_confirm'))) return;
      try { await api('DELETE', `/api/assessments/${id}`); App.goWithToast(`/candidates/${a().trainee.id}`, t('as_discarded')); } catch (err) { toast(err.message, 'error'); }
    },
    correct: () => { correcting = true; render(); },
    cancel: () => { correcting = false; result = data.result; render(); },
  });
  // Do not re-render on a language switch while typing — otherwise unsaved points would be lost.
  App.onRerender(() => data && !editable() && render());
  load();
})();

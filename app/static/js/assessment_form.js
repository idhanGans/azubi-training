/* Bewertungen: Anzeige-Helfer (Ergebnis, Status, Verlauf) + Dialog „Bewertung anlegen".
   Gerechnet wird NUR auf dem Server (app/services/scoring.py) — hier wird nur angezeigt. */
const AssessmentForm = (() => {
  const {esc, t, can, api, fmtDate, fmtNum, todayIso} = App;

  const pct = value => (value == null ? '–' : `${fmtNum(value, 1)} %`);
  const statusBadge = status => `<span class="badge ${status === 'FINAL' ? '' : 'draft'}">${esc(t('as_' + status))}</span>`;
  function passBadge(passed) {
    if (passed == null) return '';
    return `<span class="badge ${passed ? 'ok' : 'warn'}">${esc(t(passed ? 'as_passed' : 'as_failed'))}</span>`;
  }
  function delta(curr, prev) {
    if (curr == null || prev == null) return '';
    const d = Math.round((curr - prev) * 10) / 10;
    if (!d) return `<span class="trend">±0</span>`;
    return `<span class="trend ${d > 0 ? 'up' : 'down'}">${d > 0 ? '▲ +' : '▼ −'}${esc(fmtNum(Math.abs(d), 1))}</span>`;
  }

  /* Verlauf: `list` chronologisch (aelteste zuerst); Veraenderung zur vorigen abgeschlossenen Bewertung
     desselben Kandidaten mit derselben Vorlage. newestFirst dreht nur die Anzeige um. */
  function historyHtml(list, {showTrainee, newestFirst} = {}) {
    if (!list.length) return App.emptyHtml(t('as_none'));
    const last = {};
    const rows = list.map(a => {
      const key = `${a.trainee.id}-${a.template.id}`;
      const prev = a.status === 'FINAL' ? last[key] : null;
      if (a.status === 'FINAL') last[key] = a.overall_percent;
      return `<tr${a.status === 'DRAFT' ? ' class="archived"' : ''}><td class="nw">${esc(fmtDate(a.assessed_on))}</td>
        ${showTrainee ? `<td class="name"><a href="/candidates/${a.trainee.id}">${esc(a.trainee.name)}</a></td>` : ''}
        <td><a href="/assessments/${a.id}">${esc(a.template.name)}</a></td><td>${esc(a.instructor.name)}</td>
        <td class="nw"><b>${esc(pct(a.overall_percent))}</b> ${delta(a.overall_percent, prev)}</td>
        <td class="nw">${a.status === 'FINAL' ? passBadge(a.passed) : statusBadge(a.status)}</td></tr>`;
    });
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_date'))}</th>
      ${showTrainee ? `<th>${esc(t('as_candidate'))}</th>` : ''}<th>${esc(t('as_template'))}</th>
      <th>${esc(t('as_examiner'))}</th><th>${esc(t('as_result'))}</th><th>${esc(t('f_status'))}</th></tr></thead>
      <tbody>${(newestFirst ? rows.reverse() : rows).join('')}</tbody></table></div>`;
  }

  const option = (value, label, selected) => `<option value="${esc(value)}"${selected ? ' selected' : ''}>${esc(label)}</option>`;

  /* Neue Bewertung (Entwurf). trainee: {id, name, courses} fest vorgegeben, sonst Auswahl mit Suche. */
  async function create({trainee} = {}) {
    let templates, instructors = [];
    try {
      [templates, instructors] = await Promise.all([
        api('GET', '/api/assessment-templates').then(r => r.templates),
        can('candidate.view_all') ? api('GET', '/api/instructors').then(r => r.instructors.filter(i => !i.archived_at)) : [],
      ]);
    } catch (err) { App.toast(err.message, 'error'); return; }
    let candidates = trainee ? [trainee] : [];
    const chooser = can('candidate.view_all');
    const fields = [];
    if (!trainee) {
      fields.push({name: 'q', label: t('as_candidate_search'), type: 'search', placeholder: t('as_search_ph')},
                  {name: 'trainee_id', label: t('as_candidate'), type: 'select', required: true,
                   options: [{value: '', label: t('opt_choose')}]});
    }
    fields.push(
      {name: 'template_id', label: t('as_template'), type: 'select', required: true,
       options: [{value: '', label: t('opt_choose')}, ...templates.map(x => ({value: String(x.id),
         label: x.level ? `${x.name} (${x.level.code})` : x.name}))]},
      {name: 'assessed_on', label: t('f_date'), type: 'date', required: true, value: todayIso()},
      {name: 'course_id', label: t('f_course'), type: 'select', options: [{value: '', label: t('opt_none')}]});
    if (chooser) {
      fields.push({name: 'instructor_id', label: t('as_examiner'), type: 'select', required: true,
                   options: [{value: '', label: t('opt_choose')}, ...instructors.map(i => ({value: String(i.id), label: i.name}))],
                   hint: t('as_examiner_hint')});
    }
    const dlg = App.formDialog({
      title: t('as_new'), intro: t('as_new_intro'), fields, submitLabel: t('as_create'),
      onSubmit: async values => {
        const body = {trainee_id: +(trainee ? trainee.id : values.trainee_id), template_id: +values.template_id,
                      assessed_on: values.assessed_on, course_id: values.course_id ? +values.course_id : null};
        if (chooser) body.instructor_id = values.instructor_id ? +values.instructor_id : null;
        const created = await api('POST', '/api/assessments', body);
        App.goWithToast(`/assessments/${created.assessment.id}`, t('as_draft_created'));
      },
    });
    const courseSel = dlg.querySelector('[name="course_id"]');
    const instSel = dlg.querySelector('[name="instructor_id"]');
    function fillCourses(t0) {
      const courses = (t0 && t0.courses) || [];
      courseSel.innerHTML = option('', t('opt_none'), courses.length !== 1)
        + courses.map(c => option(c.id, c.name, courses.length === 1)).join('');
      courseSel.dispatchEvent(new Event('change'));
    }
    courseSel.addEventListener('change', () => {
      if (!instSel || instSel.value) return;
      const t0 = currentTrainee();
      const course = t0 && (t0.courses || []).find(c => String(c.id) === courseSel.value);
      if (course && course.instructor) instSel.value = String(course.instructor.id);
    });
    const currentTrainee = () => (trainee || candidates.find(c => String(c.id) === dlg.querySelector('[name="trainee_id"]').value));
    if (trainee) { fillCourses(trainee); return; }
    const traineeSel = dlg.querySelector('[name="trainee_id"]');
    async function search(q) {
      try {
        const res = await api('GET', `/api/candidates?per_page=100&sort=name${q ? '&q=' + encodeURIComponent(q) : ''}`);
        candidates = res.items;
        const keep = traineeSel.value;
        traineeSel.innerHTML = option('', t('opt_choose'), true)
          + candidates.map(c => option(c.id, `${c.name} (${c.candidate_no})`, String(c.id) === keep)).join('');
        fillCourses(currentTrainee());
      } catch (err) { App.showFormError(dlg.querySelector('form'), err); }
    }
    let timer = null;
    dlg.querySelector('[name="q"]').addEventListener('input', ev => { clearTimeout(timer); timer = setTimeout(() => search(ev.target.value.trim()), 250); });
    traineeSel.addEventListener('change', () => fillCourses(currentTrainee()));
    search('');
  }

  return {pct, statusBadge, passBadge, delta, historyHtml, create};
})();

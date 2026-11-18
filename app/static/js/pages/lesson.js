/* Modul-Bewertung eines Termins (Panduan Penilaian Deutschkurs): ganze Gruppe auf einer Seite — Anwesenheit,
   5 Sprech-Aspekte (1–3 Sterne), Puenktlichkeit/Mitarbeit/Hausaufgabe, Staerke(n) + Ziel(e), Notiz.
   Ein Termin kann mehrere Module abdecken: je Modul + Einheit ein Blatt (?module=&unit= in der Adresse).
   Leere Felder sind erlaubt („–"). Punkte und Level rechnet der Server (Live-Vorschau ueber
   /api/lesson-ratings/evaluate). Fuers Handy gebaut. */
(() => {
  const {$, esc, t, can, api, toast} = App;
  const V = LessonView;
  const host = $('#page');
  const sid = +host.dataset.sessionId;
  const STATUSES = ['PRESENT', 'LATE', 'ABSENT', 'EXCUSED'];
  const ATTENDED = ['PRESENT', 'LATE'];
  let data = null;
  let timer = null;
  let dirty = false;           // ungespeicherte Eingaben: Sprachwechsel baut die Seite dann NICHT neu (sonst waeren sie weg)
  const params = new URLSearchParams(location.search);
  let wanted = {module: params.get('module'), unit: params.get('unit')};

  async function load() {
    host.innerHTML = App.loadingHtml();
    const q = new URLSearchParams();
    if (wanted.module) q.set('module_id', wanted.module);
    if (wanted.unit) q.set('unit', wanted.unit);
    try {
      data = await api('GET', `/api/sessions/${sid}/lesson-ratings${q.toString() ? `?${q}` : ''}`);
      remember();
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  /* Gewaehltes Blatt in der Adresse festhalten (Neuladen/Teilen zeigt dasselbe Blatt). */
  function remember() {
    const sh = data.sheet;
    wanted = {module: String(sh.module.id), unit: String(sh.unit)};
    history.replaceState(null, '', `${location.pathname}?module=${sh.module.id}&unit=${sh.unit}`);
  }

  function openSheet(moduleId, unit) {
    if (dirty && !confirm(t('lr_leave_unsaved'))) return;
    dirty = false;
    wanted = {module: moduleId ? String(moduleId) : null, unit: unit ? String(unit) : null};
    load();
  }

  const s = () => data.session;
  const started = () => Date.parse(s().attendance_from) <= Date.now();      // Regel steht nur im Server
  const editable = () => can('assessment.create') && s().status !== 'CANCELLED' && started();

  /* Auswahl als Knoepfe (Radio): options = [{value, html, title}]; `blank` = zusaetzlicher Knopf „–" (leer lassen) */
  const pick = (name, label, options, current, blank = false) => {
    const all = blank ? [{value: '', html: '–', title: t('lr_blank')}, ...options] : options;
    const cur = current == null ? '' : String(current);
    return `<div class="lr-pick" role="radiogroup" aria-label="${esc(label)}">${all.map(o => `<label${o.title ? ` title="${esc(o.title)}"` : ''}>
      <input type="radio" name="${name}" value="${esc(o.value)}"${cur === String(o.value) ? ' checked' : ''}><span>${o.html}</span></label>`).join('')}</div>`;
  };

  function guideHtml() {
    const r = data.rules;
    const levels = n => Array.from({length: r.aspect_max - r.aspect_min + 1}, (_, i) => r.aspect_min + i).filter(x => x <= n);
    return `<details class="card"><summary><b>${esc(t('lr_guide'))}</b></summary>
      <p class="hint">${esc(t('lr_hint'))}</p>
      <div class="tbl-wrap"><table class="tbl lr-rubric"><thead><tr><th>${esc(t('lr_th_aspect'))}</th>
        ${levels(r.aspect_max).map(n => `<th>${V.stars(n, r.aspect_max)}</th>`).join('')}<th>${esc(t('lr_th_proof'))}</th></tr></thead>
        <tbody>${r.aspects.map(a => `<tr><td><b>${esc(V.aspectName(a))}</b></td>
          ${levels(r.aspect_max).map(n => `<td>${esc(t(`lr_rub_${a}_${n}`))}</td>`).join('')}
          <td class="meta">${esc(t('lr_proof_' + a))}</td></tr>`).join('')}</tbody></table></div>
      <div class="tbl-wrap"><table class="tbl lr-rubric"><thead><tr><th>${esc(t('lr_th_behavior'))}</th><th>${esc(t('lr_th_points'))}</th></tr></thead>
        <tbody>${V.BEHAVIOR.map(b => `<tr><td><b>${esc(V.behaviorName(b))}</b></td><td>${
          Array.from({length: r.behavior_max[b] + 1}, (_, n) => r.behavior_max[b] - n).map(n => `${n} = ${esc(t(`lr_beh_${b}_${n}`))}`).join(' · ')}</td></tr>`).join('')}</tbody></table></div>
      <h4 class="form-section">${esc(t('lr_th_level'))}</h4>${V.levelsHtml(r)}
      <p class="hint">${esc(t('lr_cap_rule', {c: r.capped_level}))}</p>
      <p class="meta">${esc(t('lr_doubt'))}</p>
      <p class="meta">${esc(t('lr_rules_short'))}</p></details>`;
  }

  function noteValue(e) {
    const attended = e.attendance && ATTENDED.includes(e.attendance.status);
    return attended ? (e.rating && e.rating.note) || '' : (e.attendance && e.attendance.note) || '';
  }

  function cardHtml(e) {
    const tr = e.trainee, id = tr.id, r = e.rating || {}, a = e.attendance || {}, rules = data.rules;
    const name = `${esc(tr.name)}${tr.nickname ? ` <span class="mut">(${esc(tr.nickname)})</span>` : ''}`;
    const attended = ATTENDED.includes(a.status);
    const aspectRow = asp => `<div class="flabel">${esc(V.aspectName(asp))}</div>
      ${pick(`${asp}_${id}`, `${tr.name}: ${V.aspectName(asp)}`, Array.from({length: rules.aspect_max - rules.aspect_min + 1}, (_, i) => {
        const n = rules.aspect_min + i;
        return {value: n, html: V.stars(n, rules.aspect_max), title: t(`lr_rub_${asp}_${n}`)};
      }), r[asp], true)}`;
    const behRow = b => `<div class="flabel lr-beh-${b}"${b === 'ha' && data.homework_none ? ' hidden' : ''}>${esc(V.behaviorName(b))}</div>
      <div class="lr-beh-${b}"${b === 'ha' && data.homework_none ? ' hidden' : ''}>${pick(`${b}_${id}`, `${tr.name}: ${V.behaviorName(b)}`,
        Array.from({length: rules.behavior_max[b] + 1}, (_, n) => ({value: n, html: esc(String(n)), title: t(`lr_beh_${b}_${n}`)})), r[b], true)}</div>`;
    const codeChecks = (field, label) => `<fieldset class="field lr-codes"><legend class="flabel">${esc(label)}</legend>
      <div class="checks">${rules.feedback_codes.map(c => `<label><input type="checkbox" name="${field}_${id}" value="${c}"${
        (r[field] || []).includes(c) ? ' checked' : ''}> ${esc(V.codeName(c))}</label>`).join('')}</div></fieldset>`;
    return `<article class="lr-card${attended ? '' : ' absent'}" data-trainee="${id}">
      <div class="lr-card-head"><b>${name}</b><span class="lr-result" data-result>${resultHtml(e.rating ? e.rating.result : null, a.status)}</span></div>
      ${pick(`att_${id}`, `${tr.name}: ${t('f_status')}`, STATUSES.map(st => ({value: st, html: esc(t('at_' + st))})), a.status || '')}
      <input class="input att-min" type="number" min="1" max="600" name="min_${id}" value="${esc(a.minutes_late || '')}"
        placeholder="${esc(t('at_min_ph'))}" aria-label="${esc(t('at_min_label', {name: tr.name}))}"${a.status === 'LATE' ? '' : ' hidden'}>
      <div class="lr-fields"${attended ? '' : ' hidden'}>
        <h4 class="form-section">${esc(t('lr_part_a'))}</h4><div class="lr-grid">${rules.aspects.map(aspectRow).join('')}</div>
        <h4 class="form-section">${esc(t('lr_part_b'))}</h4><div class="lr-grid">${V.BEHAVIOR.map(behRow).join('')}</div>
        <div class="lr-feedback">${codeChecks('strength', t('lr_strength'))}${codeChecks('target', t('lr_target'))}</div>
      </div>
      <label class="field"><span class="flabel" data-note-label>${esc(t(attended || !a.status ? 'lr_note' : 'lr_note_absent'))}</span>
        <textarea class="input" rows="2" maxlength="1000" name="note_${id}" aria-label="${esc(`${tr.name}: ${t('lr_note')}`)}">${esc(noteValue(e))}</textarea></label>
    </article>`;
  }

  function resultHtml(res, status) {
    if (!status) return `<span class="meta">${esc(t('lr_not_recorded'))}</span>`;
    if (!ATTENDED.includes(status)) return `<span class="meta">${esc(t('lr_absent_info'))}</span>`;
    if (!res) return `<span class="meta">${esc(t('lr_unrated'))}</span>`;
    if (!res.complete) return `<span class="meta">${esc(t('lr_incomplete'))}</span>`;
    return `${esc(V.points(res, data.rules))} ${V.levelBadge(res.level)}${res.capped ? ` <span class="meta">${esc(t('lr_capped', {c: data.rules.capped_level}))}</span>` : ''}`;
  }

  function readOnlyCard(e) {
    const tr = e.trainee, a = e.attendance;
    return `<article class="lr-card${e.rating ? '' : ' absent'}"><div class="lr-card-head"><b>${esc(tr.name)}</b>
      ${a ? AttendanceForm.statusBadge(a.status) : `<span class="meta">${esc(t('lr_not_recorded'))}</span>`}</div>
      ${e.rating ? V.compactHtml(e.rating, data.rules) : (a && a.note ? `<p class="meta wrap-text">${esc(a.note)}</p>` : '')}</article>`;
  }

  function headHtml() {
    const x = s(), sum = data.summary, sh = data.sheet;
    const same = (a, b) => a.module.id === b.module.id && a.unit === b.unit;
    const chips = data.sheets.some(o => same(o, sh)) ? data.sheets : [...data.sheets, {...sh, rated: 0}];
    const chooser = editable() && data.modules.length ? `<form class="lr-sheet-new" id="lr-sheet-new">
        <label class="field"><span class="flabel">${esc(t('page_module'))}</span><select class="input" name="module">
          ${data.modules.map(m => `<option value="${m.id}"${m.id === sh.module.id ? ' selected' : ''}>${esc(m.name)}</option>`).join('')}</select></label>
        <label class="field"><span class="flabel">${esc(t('lr_unit_label'))}</span><input class="input" type="number" name="unit"
          min="1" max="${data.unit_max}" value="${esc(sh.unit)}"></label>
        <button class="btn ghost" type="submit">${esc(t('lr_open_sheet'))}</button>
        ${sum.rated ? `<button class="btn ghost" type="button" data-move>${esc(t('lr_move'))}</button>` : ''}</form>
        ${sum.rated ? `<p class="hint">${esc(t('lr_move_hint'))}</p>` : ''}` : '';
    return `<div class="card"><div class="lr-head"><h2>${esc(x.course.name)}</h2>
        <span><b>${esc(sh.module.name)}</b> ${esc(V.unitText(sh.unit))}</span>
        <span>${esc(App.fmtSlot(x.date, x.start, x.end))}</span>${x.instructor ? `<span class="meta">${esc(x.instructor.name)}</span>` : ''}</div>
      <p class="meta">${esc(t('lr_progress', {n: sum.rated, a: sum.attended, m: sum.expected}))} ·
        <a href="/lesson-reports?course=${x.course.id}">${esc(t('lr_to_report'))}</a></p>
      <div class="lr-sheets" aria-label="${esc(t('lr_sheets'))}"><span class="meta">${esc(t('lr_sheets'))}:</span>
        ${chips.map(o => `<button type="button" class="lr-sheet${same(o, sh) ? ' on' : ''}" data-sheet="${o.module.id}:${o.unit}"
          aria-pressed="${same(o, sh)}">${esc(o.module.name)} ${esc(V.unitText(o.unit))} <span class="meta">(${o.rated})</span></button>`).join('')}</div>
      ${chooser}<p class="hint">${esc(t('lr_sheets_hint'))}</p></div>`;
  }

  function render() {
    const x = s();
    const rows = data.entries;
    let body;
    if (!editable()) {
      const why = x.status === 'CANCELLED' ? t('lr_cancelled') : !started() ? t('lr_not_yet', {t: App.fmtDateTime(x.attendance_from)})
        : t('lr_readonly');
      body = `<p class="hint">${esc(why)}</p><div class="lr-list">${rows.length ? rows.map(readOnlyCard).join('') : App.emptyHtml(t('co_no_participants'))}</div>`;
    } else {
      // Gruppenwechsel: fruehere Teilnehmer bleiben korrigierbar, nur Archivierte sind gesperrt
      const current = rows.filter(e => e.trainee.in_course && !e.trainee.archived);
      const former = rows.filter(e => !e.trainee.in_course && !e.trainee.archived);
      const locked = rows.filter(e => e.trainee.archived);
      body = `<form id="lr-form" novalidate>
        <div class="checks"><label><input type="checkbox" id="lr-nohw" name="homework_none"${data.homework_none ? ' checked' : ''}>
          ${esc(t('lr_no_homework', {n: data.rules.ha_without_homework}))}</label></div>
        <div class="lr-list">${current.length ? current.map(cardHtml).join('') : App.emptyHtml(t('co_no_participants'))}</div>
        ${former.length ? `<h3>${esc(t('at_left_course'))}</h3><p class="hint">${esc(t('lr_former_hint'))}</p>
          <div class="lr-list">${former.map(cardHtml).join('')}</div>` : ''}
        ${locked.length ? `<div class="lr-list">${locked.map(readOnlyCard).join('')}</div>` : ''}
        ${current.length || former.length ? `<div class="lr-save"><button class="btn" type="submit">${esc(t('lr_save'))}</button>
          <span class="form-error" role="alert"></span></div>` : ''}</form>`;
    }
    host.innerHTML = `${headHtml()}${guideHtml()}${body}`;
    host.querySelectorAll('[data-sheet]').forEach(b => b.addEventListener('click', () => {
      const [m, u] = b.dataset.sheet.split(':');
      openSheet(m, u);
    }));
    const chooser = $('#lr-sheet-new');
    if (chooser) chooser.addEventListener('submit', ev => {
      ev.preventDefault();
      openSheet(chooser.module.value, chooser.unit.value);
    });
    const mover = host.querySelector('[data-move]');
    if (mover) mover.addEventListener('click', () => moveSheet(chooser, mover));
    const form = $('#lr-form');
    if (form) wire(form);
  }

  /* Ganzes Blatt (alle Bewertungen) auf das gewaehlte Modul/die gewaehlte Einheit umhaengen. */
  async function moveSheet(chooser, btn) {
    const sh = data.sheet;
    const target = data.modules.find(m => String(m.id) === chooser.module.value);
    const unit = chooser.unit.value ? +chooser.unit.value : null;
    if (!target) return;
    if (dirty && !confirm(t('lr_leave_unsaved'))) return;
    const from = `${sh.module.name} ${V.unitText(sh.unit)}`, to = `${target.name} ${V.unitText(unit)}`;
    if (!confirm(t('lr_move_confirm', {from, to}))) return;
    btn.disabled = true;
    try {
      data = await api('POST', `/api/sessions/${sid}/lesson-ratings/move`,
        {module_id: sh.module.id, unit: sh.unit, to_module_id: target.id, to_unit: unit});
      dirty = false;
      remember();
      render();
      toast(t('lr_moved'));
    } catch (err) {
      toast(err.message, 'error');
      btn.disabled = false;
    }
  }

  function collect(form, forPreview) {
    const val = name => { const el = form.querySelector(`[name="${name}"]:checked`) || form.querySelector(`select[name="${name}"], textarea[name="${name}"], input[type=number][name="${name}"]`); return el ? el.value : ''; };
    const num = name => (val(name) === '' ? null : Number(val(name)));
    const codes = name => [...form.querySelectorAll(`input[type=checkbox][name="${name}"]:checked`)].map(x => x.value);
    const homeworkNone = form.querySelector('#lr-nohw').checked;
    const entries = [];
    form.querySelectorAll('.lr-card[data-trainee]').forEach(card => {
      const id = +card.dataset.trainee;
      const status = val(`att_${id}`) || null;
      const entry = {trainee_id: id, attendance: status, note: val(`note_${id}`) || null};
      if (status === 'LATE') entry.minutes_late = num(`min_${id}`);
      if (ATTENDED.includes(status)) {
        data.rules.aspects.forEach(a => { entry[a] = num(`${a}_${id}`); });
        entry.pu = num(`pu_${id}`);
        entry.mi = num(`mi_${id}`);
        entry.ha = homeworkNone ? null : num(`ha_${id}`);
        entry.strength = codes(`strength_${id}`);
        entry.target = codes(`target_${id}`);
      } else if (forPreview) {
        return;
      }
      entries.push(entry);
    });
    return {module_id: data.sheet.module.id, unit: data.sheet.unit, homework_none: homeworkNone, entries};
  }

  /* Erste unvollstaendige Karte: {card, text} oder null. Pflicht: Anwesenheit; HA, sobald bei einem Anwesenden
     etwas bewertet ist und es eine Hausaufgabe gab. Alles andere darf leer bleiben (Regel steht im Server). */
  function firstGap(form, body) {
    for (const e of body.entries) {
      const card = form.querySelector(`.lr-card[data-trainee="${e.trainee_id}"]`);
      const name = card.querySelector('.lr-card-head b').textContent.trim();
      if (!e.attendance) return {card, text: t('lr_missing_att', {name})};
      if (!ATTENDED.includes(e.attendance) || body.homework_none || e.ha != null) continue;
      const rated = [...data.rules.aspects, 'pu', 'mi'].some(k => e[k] != null) || e.strength.length || e.target.length;
      if (rated) return {card, text: t('lr_missing', {name, field: V.behaviorName('ha')})};
    }
    return null;
  }

  function schedulePreview(form) {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const body = collect(form, true);
      try {
        const res = await api('POST', '/api/lesson-ratings/evaluate', body);
        form.querySelectorAll('.lr-card[data-trainee]').forEach(card => {
          const status = (form.querySelector(`[name="att_${card.dataset.trainee}"]:checked`) || {}).value;
          card.querySelector('[data-result]').innerHTML = resultHtml(res.results[card.dataset.trainee] || null, status);
        });
      } catch (err) { /* Vorschau ist nur Hilfe — Fehler zeigt das Speichern */ }
    }, 250);
  }

  function onStatus(form, card, status) {
    const id = card.dataset.trainee;
    const attended = ATTENDED.includes(status);
    card.classList.toggle('absent', !attended);
    card.querySelector('.lr-fields').hidden = !attended;
    card.querySelector(`[name="min_${id}"]`).hidden = status !== 'LATE';
    card.querySelector('[data-note-label]').textContent = t(attended ? 'lr_note' : 'lr_note_absent');
    // Puenktlichkeit vorschlagen (anpassbar): anwesend = 1, verspaetet = 0 — nur wenn noch nichts gewaehlt ist („–")
    const chosen = form.querySelector(`[name="pu_${id}"]:checked`);
    if (attended && (!chosen || chosen.value === '')) {
      const box = form.querySelector(`[name="pu_${id}"][value="${status === 'LATE' ? 0 : 1}"]`);
      if (box) box.checked = true;
    }
  }

  function wire(form) {
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('change', ev => {
      dirty = true;
      const el = ev.target;
      if (el.id === 'lr-nohw') {
        form.querySelectorAll('.lr-beh-ha').forEach(x => { x.hidden = el.checked; });
      } else if (el.name && el.name.startsWith('att_')) {
        onStatus(form, el.closest('.lr-card'), el.value);
      }
      schedulePreview(form);
    });
    form.addEventListener('submit', async ev => {
      ev.preventDefault();
      const error = form.querySelector('.form-error');
      error.textContent = '';
      form.querySelectorAll('.lr-card.incomplete').forEach(c => c.classList.remove('incomplete'));
      const body = collect(form, false);
      const gap = firstGap(form, body);
      if (gap) {
        error.textContent = gap.text;
        gap.card.classList.add('incomplete');
        gap.card.scrollIntoView({block: 'center', behavior: 'smooth'});
        return;
      }
      const btn = form.querySelector('[type=submit]');
      btn.disabled = true;
      try {
        data = await api('PUT', `/api/sessions/${sid}/lesson-ratings`, body);
        dirty = false;
        remember();
        render();
        toast(t('lr_saved'));
      } catch (err) {
        App.showFormError(form, err);
        btn.disabled = false;
      }
    });
  }

  App.onRerender(() => data && !dirty && render());
  load();
})();

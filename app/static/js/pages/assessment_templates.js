/* Assessment templates: list with structure, editor (categories + subcategories),
   copy as a new version, archive. The server checks the rules; for categories with
   subcategories the editor only enters their sum as the max score. */
(() => {
  const {$, esc, t, can, api, fmtNum, toast} = App;
  const host = $('#page');
  let templates = null, defaultPassing = null;
  let levels = [];
  let archived = false;

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      const [tp, lv] = await Promise.all([api('GET', `/api/assessment-templates${archived ? '?archived=1' : ''}`),
                                          api('GET', '/api/catalogs/language-level')]);
      templates = tp.templates;
      defaultPassing = tp.default_passing_percent;
      levels = lv.entries;
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function structureHtml(tp) {
    return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('as_category'))}</th><th>${esc(t('as_subcategories'))}</th>
      <th class="c">${esc(t('as_max'))}</th><th class="c">${esc(t('as_weight'))}</th><th class="c">${esc(t('as_min'))}</th><th>${esc(t('tpl_skill'))}</th></tr></thead>
      <tbody>${tp.categories.map(c => `<tr><td class="name">${esc(c.name)}</td>
        <td>${c.criteria.length ? c.criteria.map(cr => `${esc(cr.name)} <span class="mut">(${esc(fmtNum(cr.max_score, 1))})</span>`).join(', ') : '–'}</td>
        <td class="c">${esc(fmtNum(c.max_score, 1))}</td><td class="c">${esc(fmtNum(c.weight, 2))}</td>
        <td class="c">${esc(c.passing_score == null ? '–' : fmtNum(c.passing_score, 1))}</td>
        <td>${esc(c.skill ? t('sk_' + c.skill) : '–')}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function cardHtml(tp) {
    const manage = can('assessment.configure');
    return `<section class="card"><div class="pghead"><h2>${esc(tp.name)}</h2>
        ${tp.level ? `<span class="badge">${esc(tp.level.code)}</span>` : ''}
        ${tp.locked ? `<span class="badge" title="${esc(t('tpl_locked_hint'))}">${App.icon('lock')} ${esc(t('tpl_locked'))}</span>` : ''}
        ${manage ? `<div class="tools">${archived ? `<button class="btn ghost sm" type="button" data-action="restore" data-id="${tp.id}">${esc(t('btn_restore'))}</button>`
          : `<button class="btn ghost sm" type="button" data-action="edit" data-id="${tp.id}">${esc(t('edit'))}</button>
          <button class="btn ghost sm" type="button" data-action="copy" data-id="${tp.id}">${esc(t('tpl_copy'))}</button>
          <button class="btn ghost sm" type="button" data-action="archive" data-id="${tp.id}">${esc(t('btn_archive'))}</button>`}</div>` : ''}</div>
      ${tp.description ? `<p class="mut">${esc(tp.description)}</p>` : ''}
      <p class="meta">${esc(t('tpl_summary', {p: fmtNum(tp.passing_percent, 1), m: fmtNum(tp.max_total, 1), n: tp.usage_count}))}</p>
      ${structureHtml(tp)}</section>`;
  }

  function render() {
    host.innerHTML = `<div class="pghead"><p class="hint inline">${esc(t('tpl_hint'))}</p><div class="tools">
        <label class="meta"><input type="checkbox" data-archived${archived ? ' checked' : ''}> ${esc(t('tm_show_archived'))}</label>
        ${can('assessment.configure') ? `<button class="btn sm" type="button" data-action="add">${esc(t('tpl_add'))}</button>` : ''}</div></div>
      ${templates.length ? templates.map(cardHtml).join('') : `<div class="card">${App.emptyHtml(t('tpl_empty'))}</div>`}`;
    host.querySelector('[data-archived]').addEventListener('change', ev => { archived = ev.target.checked; load(); });
  }

  /* ---------- Editor ---------- */
  const num = v => (v == null ? '' : String(v));

  function criterionHtml(cr, locked) {
    return `<div class="crit-row"><input class="input" data-f="cname" maxlength="120" value="${esc(cr.name || '')}" placeholder="${esc(t('tpl_sub_name'))}" aria-label="${esc(t('tpl_sub_name'))}"${locked ? ' disabled' : ''}>
      <input class="input crit-max" data-f="cmax" type="number" min="0.5" step="0.5" value="${esc(num(cr.max_score))}" aria-label="${esc(t('as_max'))}"${locked ? ' disabled' : ''}>
      ${locked ? '' : `<button class="btn ghost sm" type="button" data-remove-crit aria-label="${esc(t('co_remove'))}">${App.icon('x')}</button>`}</div>`;
  }

  const SKILLS = ['READING', 'LISTENING', 'WRITING', 'SPEAKING', 'GRAMMAR', 'VOCABULARY'];

  /* New category: "automatic" = omit the field, the server suggests the skill from the name.
     The skill stays selectable even for locked templates (changes no results). */
  function skillSelect(c) {
    const isNew = !c.id;
    const opt = (v, label) => `<option value="${v}"${(isNew ? v === 'auto' : v === (c.skill || '')) ? ' selected' : ''}>${esc(label)}</option>`;
    return `<label>${esc(t('tpl_skill'))}<select class="input" data-f="skill">${isNew ? opt('auto', t('tpl_skill_auto')) : ''}
      ${opt('', t('tpl_skill_none'))}${SKILLS.map(k => opt(k, t('sk_' + k))).join('')}</select></label>`;
  }

  function categoryHtml(c, locked) {
    const hasCrit = c.criteria && c.criteria.length;
    return `<fieldset class="cat-edit" data-id="${c.id || ''}"><legend class="sr-only">${esc(t('as_category'))}</legend>
      <div class="cat-grid">
        <label>${esc(t('f_name'))}<input class="input" data-f="name" maxlength="120" value="${esc(c.name || '')}"${locked ? ' disabled' : ''}></label>
        <label>${esc(t('as_max'))}<input class="input" data-f="max" type="number" min="0.5" step="0.5" value="${esc(num(c.max_score))}"${locked || hasCrit ? ' disabled' : ''}></label>
        <label>${esc(t('as_weight'))}<input class="input" data-f="weight" type="number" min="0.01" step="0.01" value="${esc(num(c.weight == null ? 1 : c.weight))}"${locked ? ' disabled' : ''}></label>
        <label>${esc(t('as_min'))}<input class="input" data-f="passing" type="number" min="0" step="0.5" value="${esc(num(c.passing_score))}"${locked ? ' disabled' : ''}></label>
        ${skillSelect(c)}
      </div>
      <label class="full">${esc(t('f_description'))}<input class="input" data-f="description" maxlength="1000" value="${esc(c.description || '')}"${locked ? ' disabled' : ''}></label>
      <div class="crit-list">${(c.criteria || []).map(cr => criterionHtml(cr, locked)).join('')}</div>
      ${locked ? '' : `<div class="tools"><button class="btn ghost sm" type="button" data-add-crit>${esc(t('tpl_add_sub'))}</button>
        <button class="btn ghost sm" type="button" data-remove-cat>${esc(t('tpl_remove_cat'))}</button></div>`}</fieldset>`;
  }

  /* Max score of a category with subcategories = their sum (only an input aid; the server checks it). */
  function syncMax(fieldset) {
    const crits = [...fieldset.querySelectorAll('.crit-row [data-f="cmax"]')];
    const max = fieldset.querySelector('[data-f="max"]');
    if (fieldset.querySelector('[data-f="name"]').disabled) return;
    max.disabled = crits.length > 0;
    if (crits.length) max.value = crits.reduce((s, el) => s + (Number(el.value) || 0), 0) || '';
  }

  function readCategories(dlg) {
    return [...dlg.querySelectorAll('.cat-edit')].map(fs => {
      const val = f => fs.querySelector(`[data-f="${f}"]`).value.trim();
      const skill = val('skill');
      return {name: val('name'), description: val('description'), max_score: val('max'), weight: val('weight'),
              passing_score: val('passing'), ...(skill === 'auto' ? {} : {skill: skill || null}),
              criteria: [...fs.querySelectorAll('.crit-row')].map(r => ({
                name: r.querySelector('[data-f="cname"]').value.trim(), max_score: r.querySelector('[data-f="cmax"]').value.trim()}))};
    });
  }

  function editor(tp) {
    const locked = tp && tp.locked;
    const cats = tp ? tp.categories : [{name: '', weight: 1, criteria: []}];
    const dlg = App.formDialog({
      title: t(tp ? 'tpl_edit' : 'tpl_add'),
      intro: locked ? t('tpl_locked_hint') : t('tpl_editor_hint'),
      fields: [
        {name: 'name', label: t('f_name'), required: true, maxlength: 160, value: tp ? tp.name : '', placeholder: t('tpl_name_ph')},
        {name: 'level_id', label: t('th_level'), type: 'select', value: tp && tp.level_id ? String(tp.level_id) : '',
         options: [{value: '', label: t('opt_none')}, ...levels.filter(l => l.active || (tp && l.id === tp.level_id))
           .map(l => ({value: String(l.id), label: l.name}))]},
        {name: 'description', label: t('f_description'), type: 'textarea', maxlength: 4000, value: tp ? tp.description : ''},
        {name: 'passing_percent', label: t('tpl_passing'), type: 'number', min: 0, max: 100, step: 0.1, required: true,
         value: tp ? tp.passing_percent : defaultPassing, hint: t('tpl_passing_hint')},
        {name: 'categories', label: t('tpl_categories'), type: 'custom', hint: t('tpl_categories_hint'),
         html: `<div class="cat-list">${cats.map(c => categoryHtml(c, locked)).join('')}</div>
           ${locked ? '' : `<button class="btn ghost sm" type="button" data-add-cat>${esc(t('tpl_add_cat'))}</button>`}`},
      ],
      onSubmit: async values => {
        const body = {name: values.name, description: values.description, level_id: values.level_id ? +values.level_id : null};
        if (!locked) Object.assign(body, {passing_percent: values.passing_percent, categories: readCategories(dlg)});
        else body.skills = Object.fromEntries([...dlg.querySelectorAll('.cat-edit')].map(fs => [fs.dataset.id,
          fs.querySelector('[data-f="skill"]').value || null]));
        if (tp) await api('PATCH', `/api/assessment-templates/${tp.id}`, body);
        else await api('POST', '/api/assessment-templates', body);
        toast(t('saved'));
        await load();
      },
    });
    dlg.classList.remove('narrow');
    if (locked) dlg.querySelector('[name="passing_percent"]').disabled = true;
    const list = dlg.querySelector('.cat-list');
    dlg.addEventListener('click', ev => {
      const btn = ev.target.closest('button');
      if (!btn) return;
      if (btn.hasAttribute('data-add-cat')) {
        list.insertAdjacentHTML('beforeend', categoryHtml({name: '', weight: 1, criteria: []}, false));
        list.lastElementChild.querySelector('[data-f="name"]').focus();
      } else if (btn.hasAttribute('data-remove-cat')) {
        btn.closest('.cat-edit').remove();
      } else if (btn.hasAttribute('data-add-crit')) {
        const fs = btn.closest('.cat-edit');
        fs.querySelector('.crit-list').insertAdjacentHTML('beforeend', criterionHtml({name: '', max_score: ''}, false));
        fs.querySelector('.crit-row:last-child [data-f="cname"]').focus();
        syncMax(fs);
      } else if (btn.hasAttribute('data-remove-crit')) {
        const fs = btn.closest('.cat-edit');
        btn.closest('.crit-row').remove();
        syncMax(fs);
      }
    });
    dlg.addEventListener('input', ev => { if (ev.target.dataset.f === 'cmax') syncMax(ev.target.closest('.cat-edit')); });
  }

  const find = tid => templates.find(x => x.id === tid);
  App.onActions(host, {
    add: () => editor(null),
    edit: tid => editor(find(tid)),
    copy: async tid => {
      try {
        const copy = await api('POST', `/api/assessment-templates/${tid}/copy`, {});
        toast(t('tpl_copied', {name: copy.name}));
        await load();
        editor(find(copy.id));
      } catch (err) { toast(err.message, 'error'); }
    },
    archive: async tid => {
      if (!await App.confirmDialog(t('tpl_archive_confirm', {name: find(tid).name}))) return;
      try { await api('POST', `/api/assessment-templates/${tid}/archive`, {}); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
    },
    restore: async tid => {
      try { await api('POST', `/api/assessment-templates/${tid}/restore`, {}); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
    },
  });
  App.onRerender(() => templates && render());
  load();
})();

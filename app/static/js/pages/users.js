/* Benutzerverwaltung: Team-Rollen vergeben und entziehen; Abteilungen und ihre Leiter (Zugriffsrechte der Leiter). */
(() => {
  const {$, esc, t, api, fmtDateTime, toast} = App;
  const host = $('#page');
  let data = null, departments = [];

  async function load() {
    host.innerHTML = App.loadingHtml();
    try {
      [data, {departments}] = await Promise.all([api('GET', '/api/users'), api('GET', '/api/departments')]);
      render();
    } catch (err) {
      App.showError(host, err, load);
    }
  }

  function render() {
    const envRows = data.env_super_admins.map(u => `<tr><td>${esc(u)}</td><td>${esc(t('role_SUPER_ADMIN'))}</td>
      <td colspan="2" class="mut">${esc(t('us_env'))}</td><td></td></tr>`).join('');
    const rows = data.assignments.map(a => `<tr><td>${esc(a.username)}</td><td>${esc(t('role_' + a.role))}</td>
      <td>${esc(a.created_by || '–')}</td><td class="nw">${esc(fmtDateTime(a.created_at))}</td>
      <td><button class="btn danger sm" type="button" data-action="revoke" data-id="${a.id}">${esc(t('us_revoke'))}</button></td></tr>`).join('');
    host.innerHTML = `<div class="card">
      <div class="pghead"><div class="tools"><button class="btn sm" type="button" data-action="add">${esc(t('us_add'))}</button></div></div>
      <p class="hint">${esc(t('us_hint'))}</p>
      ${envRows || rows ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_login'))}</th>
        <th>${esc(t('f_role'))}</th><th>${esc(t('us_by'))}</th><th>${esc(t('us_at'))}</th><th>${esc(t('th_actions'))}</th></tr></thead>
        <tbody>${envRows}${rows}</tbody></table></div>` : App.emptyHtml(t('us_empty'))}
    </div>
    <div class="card section-gap">
      <div class="pghead"><h3>${esc(t('dp_title'))}</h3>
        <div class="tools"><button class="btn sm" type="button" data-action="addDept">${esc(t('dp_add'))}</button></div></div>
      <p class="hint">${esc(t('dp_hint'))}</p>
      ${departments.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>${esc(t('f_department'))}</th>
        <th class="c">${esc(t('dp_trainees'))}</th><th>${esc(t('ov_leaders'))}</th><th>${esc(t('f_status'))}</th><th>${esc(t('th_actions'))}</th></tr></thead>
        <tbody>${departments.map(d => `<tr${d.active ? '' : ' class="archived"'}><td>${esc(d.name)}</td><td class="c">${d.trainee_count}</td>
          <td>${d.leaders.length ? esc(d.leaders.join(', ')) : `<span class="mut">${esc(t('dp_no_leaders'))}</span>`}</td>
          <td>${esc(t(d.active ? 'active' : 'inactive'))}</td>
          <td><button class="btn ghost sm" type="button" data-action="editDept" data-id="${d.id}">${esc(t('edit'))}</button></td></tr>`).join('')}
        </tbody></table></div>` : App.emptyHtml(t('dp_empty'))}
    </div>`;
  }

  function departmentDialog(d) {
    App.formDialog({title: t(d ? 'dp_edit_title' : 'dp_add'), intro: t('dp_dialog_hint'), fields: [
      {name: 'name', label: t('f_department'), required: true, maxlength: 80, value: d ? d.name : ''},
      {name: 'leaders', label: t('ov_leaders'), type: 'textarea', rows: 2, value: d ? d.leaders.join(', ') : '',
       placeholder: 'galih_santoso, markus_weber', hint: t('dp_leaders_hint')},
      ...(d ? [{name: 'active', label: t('f_status'), type: 'select', value: d.active ? 'true' : 'false',
                options: [{value: 'true', label: t('active')}, {value: 'false', label: t('inactive')}]}] : []),
    ], onSubmit: async v => {
      const body = {name: v.name, leaders: v.leaders.split(/[\s,;]+/).filter(Boolean)};
      if (d) body.active = v.active === 'true';
      if (d) await api('PATCH', `/api/departments/${d.id}`, body); else await api('POST', '/api/departments', body);
      toast(t('saved'));
      await load();
    }});
  }

  App.onActions(host, {
    addDept: () => departmentDialog(null),
    editDept: id => departmentDialog(departments.find(d => d.id === id)),
    add: () => App.formDialog({title: t('us_add_title'), fields: [
      {name: 'username', label: t('f_login'), required: true, maxlength: 120},
      {name: 'role', label: t('f_role'), type: 'select', required: true, value: '',
       options: [{value: '', label: '–'}, ...data.assignable_roles.map(r => ({value: r, label: t('role_' + r)}))]},
    ], onSubmit: async v => { await api('POST', '/api/users', v); toast(t('saved')); await load(); }}),
    revoke: async id => {
      const a = data.assignments.find(x => x.id === id);
      if (!await App.confirmDialog(t('us_confirm_revoke', {role: t('role_' + a.role), name: a.username}))) return;
      try { await api('DELETE', `/api/users/${id}`); toast(t('saved')); await load(); } catch (err) { toast(err.message, 'error'); }
    },
  });
  App.onRerender(() => data && render());
  load();
})();
